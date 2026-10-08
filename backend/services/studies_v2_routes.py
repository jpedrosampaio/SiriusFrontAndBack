from collections import Counter,defaultdict
from datetime import date,datetime,timezone
from uuid import UUID
from fastapi import APIRouter,Request,HTTPException
from sqlalchemy import select,func,Date,or_
from db.session import unit_of_work
from db.models.studies import StudyArea,StudyProgram,StudyTarget,Notebook,StudyTopic,TopicProgress,StudySession,StudyPlan,StudyPlanEntry,QuestionAttempt,ReviewEvent,Flashcard,StudyNote,StudyDraft
from db.models.exams import Question,Exam,ExamQuestion
from db.models.files import FileRecord,EditalAnalysis
from services.auth_routes import account
from services.study_activity_routes import mutate
from services.studies_catalog import owned,notebooks as catalog_notebooks,public as catalog_public
from services.study_workspace import entry_json
from services.study_evidence import attempts,latest_reviews,attempt_json
from services.time import local_today
from study_mastery import mastery,adaptive_review,topic_priority
from studies_v2 import TargetInput,AttemptInput,ErrorUpdate,BlueprintInput
from db.models.identity import User
from services.preparation_state import preparation_state
from question_intelligence import error_bank,forensic_clusters
from db.models.question_insights import QuestionInsight
from pydantic import BaseModel
from typing import Literal

router=APIRouter(prefix='/study/v2')


def identity(value):
    try: return UUID(value)
    except (ValueError,TypeError): raise HTTPException(422,'Identificador inválido.') from None


def target_json(row,program):
    return {'target_id':str(row.id),'user_id':str(row.user_id),'program_id':str(row.program_id),'name':row.name or program.name,
        'kind':row.kind,'institution':row.institution or '','board':row.board or '','edition':row.edition or '',
        'position':row.position or '','exam_date':(row.exam_date or program.target_date).isoformat() if row.exam_date or program.target_date else None,
        'provenance':'user_provided' if row.metadata_origin=='manual' else row.metadata_origin,'created_at':row.created_at.isoformat()}


@router.get('/targets')
async def targets(request: Request):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        owner=await session.get(User,uid)
        primary=(owner.preferences or {}).get('primary_preparation_id')
        rows=(await session.execute(select(StudyProgram,StudyTarget).outerjoin(StudyTarget,
            (StudyTarget.program_id==StudyProgram.id)&(StudyTarget.user_id==StudyProgram.user_id)).where(
            StudyProgram.user_id==uid,StudyProgram.archived_at.is_(None)).order_by(StudyProgram.created_at.desc()))).all()
        return [{**(target_json(target,program) if target else {'target_id':'program:'+str(program.id),'program_id':str(program.id),
            'name':program.name,'kind':'custom','exam_date':program.target_date.isoformat() if program.target_date else None,
            'legacy':True,'provenance':'user_provided'}), 'is_primary':str(program.id)==primary} for program,target in rows]


@router.put('/programs/{program_id}/primary')
async def primary_preparation(request: Request,program_id: UUID):
    if not request.headers.get('Idempotency-Key'): raise HTTPException(422,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        await owned(session,StudyProgram,user.id,program_id)
        user.preferences={**(user.preferences or {}),'primary_preparation_id':str(program_id)}
        return {'preparation_id':str(program_id),'is_primary':True}
    return await mutate(request,['primary-preparation',str(program_id)],apply)


@router.get('/programs/{program_id}/state')
async def preparation_view(request: Request,program_id: UUID):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        program=await owned(session,StudyProgram,uid,program_id)
        return await preparation_state(session,uid,program,user['timezone'],local_today(user['timezone']))


@router.post('/targets')
async def target_create(request: Request,body: TargetInput):
    if not request.headers.get('Idempotency-Key'): raise HTTPException(422,'Idempotency-Key obrigatório.')
    if not body.name.strip(): raise HTTPException(422,'Informe o nome.')
    async def apply(session,user):
        if body.program_id:
            program=await owned(session,StudyProgram,user.id,identity(body.program_id))
            row=await session.scalar(select(StudyTarget).where(StudyTarget.user_id==user.id,StudyTarget.program_id==program.id))
            if row: return target_json(row,program)
        else:
            area=StudyArea(user_id=user.id,name=body.name.strip(),icon='book',color='#ad9bff'); session.add(area); await session.flush()
            program=StudyProgram(user_id=user.id,area_id=area.id,name=body.name.strip(),target_date=body.exam_date)
            session.add(program); await session.flush()
        row=StudyTarget(user_id=user.id,program_id=program.id,name=body.name.strip(),kind=body.kind,institution=body.institution,
            board=body.board,edition=body.edition,position=body.position,exam_date=body.exam_date)
        session.add(row); await session.flush(); return target_json(row,program)
    return await mutate(request,['create-study-target',body.model_dump(mode='json')],apply)


@router.get('/today')
async def today_view(request: Request):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        rows=(await session.execute(select(StudyPlanEntry,StudyPlan.program_id).join(StudyPlan,
            (StudyPlan.id==StudyPlanEntry.plan_id)&(StudyPlan.user_id==StudyPlanEntry.user_id)).join(StudyProgram,
            (StudyProgram.id==StudyPlan.program_id)&(StudyProgram.user_id==StudyPlan.user_id))
            .where(StudyPlanEntry.user_id==uid,StudyPlanEntry.date==today,StudyProgram.archived_at.is_(None)).order_by(StudyPlanEntry.id))).all()
        minutes=await session.scalar(select(func.coalesce(func.sum(StudySession.duration_minutes),0))
            .where(StudySession.user_id==uid,StudySession.date==today,StudySession.completed.is_(True)))
        entries=[{**entry_json(row),'program_id':str(pid)} for row,pid in rows]; pending=[r for r in entries if not r['completed']]
    return {'date':today.isoformat(),'next_session':pending[0] if pending else None,'pending':pending[:20],
        'planned_minutes':sum(r['minutes'] for r in entries),'studied_minutes':minutes}


@router.post('/attempts')
async def attempt_create(request: Request,body: AttemptInput):
    if not request.headers.get('Idempotency-Key'): raise HTTPException(422,'Idempotency-Key obrigatório.')
    if body.skipped and (body.correct or body.answer.strip()):raise HTTPException(422,'Questão pulada não pode ter resposta nem acerto.')
    async def apply(session,user):
        notebook=await owned(session,Notebook,user.id,identity(body.notebook_id))
        topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==user.id,StudyTopic.notebook_id==notebook.id,
            StudyTopic.topic_key==body.topic_key,StudyTopic.archived_at.is_(None)))
        if topic is None: raise HTTPException(422,'Assunto não encontrado.')
        if body.internal_question_id:
            question=await session.scalar(select(Question).where(Question.user_id==user.id,
                Question.id==identity(body.internal_question_id),Question.notebook_id==notebook.id,Question.topic_id==topic.id))
            if question is None:raise HTTPException(404,'Questão não encontrada neste assunto.')
        else:
            question=Question(user_id=user.id,notebook_id=notebook.id,topic_id=topic.id,statement=body.question,
                question_type='manual',source='manual',provenance={'board':body.board,'exam':body.exam,'position':body.position,
                    'provider':'manual','origin':'user_created','generated_by_ai':False})
            session.add(question); await session.flush()
        row=QuestionAttempt(user_id=user.id,notebook_id=notebook.id,topic_id=topic.id,question_id=question.id,total=1,correct=int(body.correct),
            answer=body.answer,duration_seconds=body.seconds,source=body.source,error_cause=None if body.correct else body.error_reason,
            answered_at=datetime.now(timezone.utc),evidence={'board':body.board,'exam':body.exam,'position':body.position,
                'difficulty':body.difficulty,'external_question_id':body.question_id,'confidence':body.confidence,
                'skipped':body.skipped,'answered':not body.skipped,'changed_answer':body.changed_answer})
        previous=await attempts(session,user.id,user.timezone,notebook_id=notebook.id,topic_id=topic.id,limit=499)
        today=local_today(user.timezone)
        review_day=func.timezone(user.timezone,ReviewEvent.reviewed_at).cast(Date)
        count=await session.scalar(select(func.count(func.distinct(review_day))).where(ReviewEvent.user_id==user.id,ReviewEvent.topic_id==topic.id,review_day<today))
        session.add(row); await session.flush()
        document=attempt_json(row,notebook,topic,question,user.timezone)
        if body.skipped:return {**document,'review':None}
        review=adaptive_review(previous+[document],today,previous_reviews=count,difficulty=body.difficulty)
        session.add(ReviewEvent(user_id=user.id,topic_id=topic.id,reviewed_at=datetime.now(timezone.utc),
            result=review['reason'],next_review=date.fromisoformat(review['due_date'])))
        return {**document,'review':review}
    return await mutate(request,['study-attempt',body.model_dump()],apply)


@router.get('/programs/{program_id}/question-intelligence')
async def question_intelligence_view(request: Request,program_id: UUID):
    user=await account(request);uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await owned(session,StudyProgram,uid,program_id)
        rows=await attempts(session,uid,user['timezone'],program_id=program_id,limit=5000,active_topics=True)
        current_fingerprints={item['fingerprint'] for item in forensic_clusters(rows)}
        insights=(await session.scalars(select(QuestionInsight).where(QuestionInsight.user_id==uid,
            QuestionInsight.program_id==program_id,QuestionInsight.status=='active',QuestionInsight.fingerprint.in_(current_fingerprints)).order_by(QuestionInsight.updated_at.desc(),QuestionInsight.id).limit(50))).all()
        reviews=await latest_reviews(session,uid,program_id=program_id)
    bank=error_bank(rows);related={(r['notebook_id'],r['topic_key']) for r in bank['items']}
    return {'error_bank':bank,'suggestions':[{'insight_id':str(row.id),'status':row.status,**row.details} for row in insights],
        'related_reviews':[r for r in reviews if (r['notebook_id'],r['topic_key']) in related][:100],'truncated':len(rows)>=5000,'sample_limit':5000,'requires_confirmation':True}


@router.post('/programs/{program_id}/question-intelligence/analyze')
async def analyze_question_errors(request: Request,program_id: UUID):
    if not request.headers.get('Idempotency-Key'):raise HTTPException(422,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        await owned(session,StudyProgram,user.id,program_id)
        rows=await attempts(session,user.id,user.timezone,program_id=program_id,limit=5000,active_topics=True)
        suggestions=forensic_clusters(rows)
        for suggestion in suggestions:suggestion['computed_at']=datetime.now(timezone.utc).isoformat()
        fingerprints={item['fingerprint'] for item in suggestions}
        existing=(await session.scalars(select(QuestionInsight).where(QuestionInsight.user_id==user.id,QuestionInsight.program_id==program_id,
            or_(QuestionInsight.status=='active',QuestionInsight.fingerprint.in_(fingerprints))))).all()
        indexed={row.fingerprint:row for row in existing}
        for row in existing:
            if row.status=='active':row.status='superseded'
        results=[]
        for suggestion in suggestions:
            row=indexed.get(suggestion['fingerprint'])
            if row is None:
                row=QuestionInsight(user_id=user.id,program_id=program_id,fingerprint=suggestion['fingerprint'],status='active',details=suggestion)
                session.add(row)
            else:
                row.details=suggestion
                if row.status!='dismissed':row.status='active'
            results.append(row)
        await session.flush()
        return {'suggestions':[{'insight_id':str(row.id),'status':row.status,**row.details} for row in results if row.status=='active'],
            'truncated':len(rows)>=5000,'facts_changed':False}
    return await mutate(request,['question-forensics',str(program_id)],apply)


class InsightStatus(BaseModel):
    status: Literal['active','dismissed']


@router.patch('/programs/{program_id}/question-intelligence/{insight_id}')
async def insight_status(request: Request,program_id: UUID,insight_id: UUID,body: InsightStatus):
    if not request.headers.get('Idempotency-Key'):raise HTTPException(422,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        await owned(session,StudyProgram,user.id,program_id)
        row=await session.scalar(select(QuestionInsight).where(QuestionInsight.user_id==user.id,
            QuestionInsight.program_id==program_id,QuestionInsight.id==insight_id))
        if row is None:raise HTTPException(404,'Sugestão não encontrada.')
        row.status=body.status;return {'insight_id':str(row.id),'status':row.status,'facts_changed':False}
    return await mutate(request,['question-insight-status',str(program_id),str(insight_id),body.status],apply)


@router.patch('/attempts/{attempt_id}/error')
async def error_update(request: Request,attempt_id: UUID,body: ErrorUpdate):
    async def apply(session,user):
        row=await session.scalar(select(QuestionAttempt).where(QuestionAttempt.user_id==user.id,QuestionAttempt.id==attempt_id,
            QuestionAttempt.correct==0,QuestionAttempt.total==1,QuestionAttempt.question_id.is_not(None)))
        if row is None: raise HTTPException(404,'Erro não encontrado.')
        row.error_cause=body.reason; return {'reason':body.reason}
    return await mutate(request,['attempt_error',str(attempt_id),body.model_dump()],apply)


@router.get('/performance')
async def performance(request: Request,program_id: UUID | None = None):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        if program_id: await owned(session,StudyProgram,uid,program_id)
        rows=await attempts(session,uid,user['timezone'],program_id=program_id)
    groups=defaultdict(list); days=defaultdict(lambda:{'total':0,'correct':0})
    for row in rows:
        groups[(row['notebook_id'],row['topic_key'])].append(row)
        days[row['date']]['total']+=1; days[row['date']]['correct']+=int(row['correct'])
    errors=[r for r in rows if not r['correct']]
    return {'topics':[{'notebook_id':key[0],'topic_key':key[1],'title':evidence[0]['title'],**mastery(evidence,today)} for key,evidence in groups.items()],
        'summary':mastery(rows,today),'error_causes':dict(Counter(r['error_reason'] or 'unclassified' for r in errors)),
        'errors':errors[:100],'trend':[{'date':day,**counts,'accuracy':round(100*counts['correct']/counts['total'],1)} for day,counts in sorted(days.items())[-30:]],
        'truncated':len(rows)==5000,'sample_limit':5000}


@router.get('/library')
async def library(request: Request,program_id: UUID | None = None,notebook_id: UUID | None = None):
    user=await account(request); uid=UUID(user['user_id']); items=[]
    async with unit_of_work() as session:
        if program_id: await owned(session,StudyProgram,uid,program_id)
        notebooks=await catalog_notebooks(session,uid,program_id=program_id)
        ids=[UUID(n['notebook_id']) for n in notebooks if not notebook_id or n['notebook_id']==str(notebook_id)]
        for model,kind,title_field,text_field in ((StudyNote,'note','title','content'),(StudyDraft,'summary','topic_key','text'),(Flashcard,'flashcard','front','back')):
            query=select(model).where(model.user_id==uid,model.notebook_id.in_(ids))
            if model is Flashcard: query=query.where(Flashcard.archived_at.is_(None))
            rows=(await session.scalars(query.order_by(model.created_at.desc(),model.id).limit(300))).all()
            for row in rows:
                key=row.topic_key if model is StudyDraft else str(row.id)
                items.append({'id':f'{kind}:{row.notebook_id}:{key}','kind':kind,'title':getattr(row,title_field)[:200],
                    'excerpt':getattr(row,text_field)[:1500],'notebook_id':str(row.notebook_id),'topic_key':getattr(row,'topic_key',None),'provenance':'user_provided'})
                if model is StudyNote:
                    for link in row.links[:30]:
                        url=str(link.get('url',''))
                        if url.startswith('https://'): items.append({'id':f'link:{len(items)}','kind':'link','title':str(link.get('title') or url)[:200],
                            'url':url,'notebook_id':str(row.notebook_id),'provenance':'external'})
        if not program_id and not notebook_id:
            files=(await session.scalars(select(FileRecord).where(FileRecord.user_id==uid).order_by(FileRecord.created_at.desc()).limit(100))).all()
            items.extend({'id':str(row.id),'kind':'file','title':row.filename,'attachment_id':str(row.id),'provenance':row.details.get('provenance','extracted')} for row in files)
            analyses=(await session.execute(select(EditalAnalysis,FileRecord.filename).outerjoin(FileRecord,
                (FileRecord.id==EditalAnalysis.file_id)&(FileRecord.user_id==EditalAnalysis.user_id)).where(EditalAnalysis.user_id==uid)
                .order_by(EditalAnalysis.created_at.desc()).limit(100))).all()
            items.extend({'id':str(row.id),'kind':'edital','title':filename or row.filename or 'Edital','analysis_id':str(row.id),'provenance':'extracted'} for row,filename in analyses)
    return {'items':items[:1000],'notebooks':notebooks,'truncated':len(items)>=1000,
        'scope':'materiais indexados e notas; fontes externas identificadas separadamente'}


async def coverage(session,uid,ids):
    rows=(await session.execute(select(StudyTopic.notebook_id,StudyTopic.topic_key,TopicProgress.studied).outerjoin(TopicProgress,
        (TopicProgress.topic_id==StudyTopic.id)&(TopicProgress.user_id==StudyTopic.user_id)).where(StudyTopic.user_id==uid,
        StudyTopic.notebook_id.in_(ids),StudyTopic.archived_at.is_(None)))).all()
    return {(str(nid),key):bool(studied) for nid,key,studied in rows}


@router.get('/programs/{program_id}/recommendations')
async def recommendations(request: Request,program_id: UUID):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        program=await owned(session,StudyProgram,uid,program_id)
        notebooks=await catalog_notebooks(session,uid,program_id=program_id)
        rows=await attempts(session,uid,user['timezone'],program_id=program_id)
        reviews=await latest_reviews(session,uid,program_id=program_id,due=today)
        studied=await coverage(session,uid,[UUID(n['notebook_id']) for n in notebooks])
        days_left=(program.target_date-today).days if program.target_date else None
    groups=defaultdict(list)
    for row in rows: groups[(row['notebook_id'],row['topic_key'])].append(row)
    overdue={(row['notebook_id'],row['topic_key']) for row in reviews}; suggestions=[]
    for nb in notebooks:
        for index,topic in enumerate(nb['conteudo_programatico'] or nb['topicos']):
            key=(nb['notebook_id'],str(index)); evidence=groups[key]; estimate=mastery(evidence,today)
            priority=topic_priority(weight=nb['weight'],question_count=nb['num_questoes_edital'],estimate=estimate['score'],
                errors=sum(not row['correct'] for row in evidence),overdue=key in overdue,studied=studied.get(key,False),days_left=days_left)
            suggestions.append({'notebook_id':key[0],'topic_key':key[1],'title':topic.get('assunto','') if isinstance(topic,dict) else str(topic),
                'discipline':nb['name'],'mastery':estimate,**priority})
    return {'items':sorted(suggestions,key=lambda row:(-row['priority'],row['title']))[:10],'requires_confirmation':True,
        'notice':'Sugestões calculadas com pesos registrados, respostas e revisões. O plano atual não foi alterado.'}


@router.get('/programs/{program_id}/overview')
async def overview(request: Request,program_id: UUID):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        program=await owned(session,StudyProgram,uid,program_id)
        target=await session.scalar(select(StudyTarget).where(StudyTarget.user_id==uid,StudyTarget.program_id==program_id))
        notebooks=await catalog_notebooks(session,uid,program_id=program_id)
        covered=await coverage(session,uid,[UUID(row['notebook_id']) for row in notebooks])
        rows=await attempts(session,uid,user['timezone'],program_id=program_id)
        upcoming=await session.scalar(select(StudyPlanEntry).join(StudyPlan,
            (StudyPlan.id==StudyPlanEntry.plan_id)&(StudyPlan.user_id==StudyPlanEntry.user_id))
            .where(StudyPlanEntry.user_id==uid,StudyPlan.program_id==program_id,StudyPlanEntry.completed.is_(False),StudyPlanEntry.date>=today)
            .order_by(StudyPlanEntry.date,StudyPlanEntry.id).limit(1))
        groups=defaultdict(list)
        for row in rows: groups[(row['notebook_id'],row['topic_key'])].append(row)
        topics=[{'title':evidence[0]['title'],'notebook_id':key[0],'topic_key':key[1],**mastery(evidence,today)} for key,evidence in groups.items()]
        total=sum(row['total_questions'] for row in notebooks); correct=sum(row['correct_questions'] for row in notebooks)
        target_date=(target.exam_date if target else None) or program.target_date
        return {'target':target_json(target,program) if target else {},'target_date':target_date.isoformat() if target_date else None,
            'days_remaining':(target_date-today).days if target_date else None,
            'coverage':{'studied':sum(covered.values()),'total':len(covered),'percent':round(100*sum(covered.values())/len(covered)) if covered else None},
            'mastery':mastery(rows,today),'questions':total,'accuracy':round(100*correct/total,1) if total else None,
            'study_minutes':sum(row['total_study_time_minutes'] for row in notebooks),'weakest':min(topics,key=lambda row:row['score']) if topics else None,
            'next_session':entry_json(upcoming) if upcoming else None}


@router.get('/reviews')
async def reviews(request: Request,program_id: UUID | None = None):
    user=await account(request); uid=UUID(user['user_id']); today=local_today(user['timezone'])
    async with unit_of_work() as session:
        if program_id: await owned(session,StudyProgram,uid,program_id)
        due=await latest_reviews(session,uid,program_id=program_id,due=today,limit=300)
        queue=[{**row,'kind':'topic'} for row in due]; due_topics={(r['notebook_id'],r['topic_key']):r['due_date'] for r in due}
        recent=await attempts(session,uid,user['timezone'],program_id=program_id,limit=2000)
        seen=set(); errors=0
        for row in recent:
            key=(row['notebook_id'],row['topic_key'],row['question_id'] or row['question'])
            if key in seen: continue
            seen.add(key); day=due_topics.get(key[:2])
            if not row['correct'] and day:
                queue.append({**row,'kind':'wrong_question','due_date':day,'reason':'Última resposta incorreta; refaça a questão e revise o assunto.'})
                errors+=1
                if errors>=100: break
        query=select(Flashcard).join(Notebook,(Notebook.id==Flashcard.notebook_id)&(Notebook.user_id==Flashcard.user_id))
        query=query.where(Flashcard.user_id==uid,Flashcard.archived_at.is_(None),Notebook.archived_at.is_(None),Flashcard.next_review<=today)
        if program_id: query=query.where(Notebook.program_id==program_id)
        cards=(await session.scalars(query.order_by(Flashcard.next_review,Flashcard.id).limit(100))).all()
        queue.extend({'kind':'flashcard','title':row.front,'notebook_id':str(row.notebook_id),'card_id':str(row.id),
            'due_date':row.next_review.isoformat(),'reason':'Revisão do cartão agendada para hoje ou antes.'} for row in cards)
    return {'items':sorted(queue,key=lambda row:row['due_date']),'date':today.isoformat()}


@router.get('/programs/{program_id}/blueprint')
async def blueprint_get(request: Request,program_id: UUID):
    from study_blueprint import blueprint
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await owned(session,StudyProgram,uid,program_id)
        return blueprint(await catalog_notebooks(session,uid,program_id=program_id))


@router.post('/programs/{program_id}/blueprint/simulado')
async def blueprint_create(request: Request,program_id: UUID,body: BlueprintInput):
    from study_blueprint import blueprint,assemble
    if not request.headers.get('Idempotency-Key'): raise HTTPException(422,'Idempotency-Key obrigatório.')
    async def apply(session,user):
        program=await owned(session,StudyProgram,user.id,program_id)
        notebooks=await catalog_notebooks(session,user.id,program_id=program_id); plan=blueprint(notebooks)
        if not plan['complete'] or not 1<=plan['total']<=200: raise HTTPException(422,'Distribuição incompleta ou fora do limite de 1 a 200 questões. Confira a análise do edital.')
        rows=(await session.execute(select(ExamQuestion,Question,Exam,StudyTopic).join(Exam,
            (Exam.id==ExamQuestion.exam_id)&(Exam.user_id==ExamQuestion.user_id)).join(Question,
            (Question.id==ExamQuestion.question_id)&(Question.user_id==ExamQuestion.user_id)).outerjoin(StudyTopic,
            (StudyTopic.id==Question.topic_id)&(StudyTopic.user_id==Question.user_id))
            .where(ExamQuestion.user_id==user.id,Exam.program_id==program_id,Exam.archived_at.is_(None)).order_by(Exam.id,ExamQuestion.position))).all()
        exams={}
        names={row['notebook_id']:row['name'] for row in notebooks}
        for link,q,exam,topic in rows:
            doc=exams.setdefault(str(exam.id),{'simulado_id':str(exam.id),'questions':[]})
            doc['questions'].append({'question_text':q.statement,'question_type':q.question_type,'options':q.options,
                'correct_answer':q.correct_answer,'explanation':q.explanation,'disciplina':q.provenance.get('disciplina') or names.get(str(q.notebook_id),''),
                'notebook_id':str(q.notebook_id) if q.notebook_id else None,'topic_key':topic.topic_key if topic else None})
        selected=assemble(plan['distribution'],list(exams.values()),request.headers['Idempotency-Key'])
        exam=Exam(user_id=user.id,program_id=program_id,area_id=program.area_id,title=body.title,description='Montado com questões existentes conforme a distribuição extraída do edital.',
            kind='simulado',status='ready',duration_minutes=body.duration_minutes,blueprint=plan,provenance={'source_type':'edital_blueprint','duration_provenance':'user_provided','question_type':'misto'})
        session.add(exam); await session.flush()
        for index,values in enumerate(selected):
            topic=None
            if values.get('topic_key'):
                topic=await session.scalar(select(StudyTopic).where(StudyTopic.user_id==user.id,StudyTopic.notebook_id==UUID(values['notebook_id']),
                    StudyTopic.topic_key==values['topic_key'],StudyTopic.archived_at.is_(None)))
            if topic is None: values.pop('topic_key',None)
            question=Question(user_id=user.id,notebook_id=UUID(values['notebook_id']),topic_id=topic.id if topic else None,
                statement=values['question_text'],question_type=values.get('question_type','multipla_escolha'),options=values.get('options',[]),
                correct_answer=values.get('correct_answer'),explanation=values.get('explanation'),source='edital_blueprint',
                provenance={key:values[key] for key in ('disciplina','source_simulado_id','source_question_index') if key in values})
            session.add(question); await session.flush()
            session.add(ExamQuestion(user_id=user.id,exam_id=exam.id,question_id=question.id,position=index,weight=values['weight']))
        return {'simulado_id':str(exam.id),'user_id':str(user.id),'program_id':str(program_id),'area_id':str(program.area_id),
            'title':exam.title,'description':exam.description,'source_type':'edital_blueprint','questions':selected,'total_questions':len(selected),
            'questions_count':len(selected),'question_type':'misto','status':'ready','duration_minutes':body.duration_minutes,
            'duration_provenance':'user_provided','blueprint':plan,'created_at':exam.created_at.isoformat()}
    return await mutate(request,['blueprint-simulado',str(program_id),body.model_dump()],apply)

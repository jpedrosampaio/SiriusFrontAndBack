from types import SimpleNamespace
from typing import Optional
from fastapi import Cookie
from datetime import time
from uuid import UUID
from typing import Literal
from fastapi import APIRouter,Request,HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel,model_validator
from sqlalchemy import select,delete,func
from db.session import unit_of_work
from db.models.studies import StudyProgram,Notebook,StudySchedule,StudyTopic,TopicProgress,StudySession,StudyNote,Flashcard
from services.auth_routes import account
from services.study_activity_routes import mutate
from services import studies_catalog as catalog
from services.edital_programs import DAYS,LABELS,settings,schedules
from services.time import local_today
from study_resources import positive_number

router=APIRouter(prefix='/study')


def schedule_json(row,book):
    return jsonable_encoder({'schedule_id':row.id,'user_id':row.user_id,'notebook_id':row.notebook_id,'program_id':book.program_id,
        'day_of_week':row.day_of_week,'start_time':row.start_time.strftime('%H:%M'),'end_time':row.end_time.strftime('%H:%M'),
        'repeat':row.repeat,'tipo_estudo':row.tipo_estudo,'prioridade':row.prioridade,'assuntos_foco':row.assuntos_foco,
        'created_at':row.created_at,'disciplina_nome':book.name,'disciplina_color':book.color,'weight':book.weight})


async def get_program(uid,pid):
    async with unit_of_work() as session: return catalog.public(await catalog.owned(session,StudyProgram,UUID(uid),UUID(str(pid))))


async def get_notebooks(uid,pid):
    async with unit_of_work() as session: return await catalog.notebooks(session,UUID(uid),program_id=UUID(str(pid)))


async def get_schedules(uid,pid=None):
    async with unit_of_work() as session:
        query=select(StudySchedule,Notebook).join(Notebook,(Notebook.id==StudySchedule.notebook_id)&(Notebook.user_id==StudySchedule.user_id))
        query=query.where(StudySchedule.user_id==UUID(uid),Notebook.archived_at.is_(None))
        if pid: query=query.where(Notebook.program_id==UUID(str(pid)))
        return [schedule_json(row,book) for row,book in (await session.execute(query.order_by(StudySchedule.created_at,StudySchedule.id))).all()]


async def get_progress(uid,ids):
    async with unit_of_work() as session:
        rows=(await session.execute(select(StudyTopic,TopicProgress).join(TopicProgress,
            (TopicProgress.topic_id==StudyTopic.id)&(TopicProgress.user_id==StudyTopic.user_id)).where(
                StudyTopic.user_id==UUID(uid),StudyTopic.notebook_id.in_([UUID(i) for i in ids]),StudyTopic.archived_at.is_(None)))).all()
        result={}
        for topic,row in rows:
            result.setdefault(str(topic.notebook_id),{})[topic.topic_key]={'studied':row.studied,'reviewed':row.reviewed,'mastered':row.confident}
        return result


class ScheduleBody(BaseModel):
    notebook_id: UUID
    day_of_week: Literal['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
    start_time: time
    end_time: time
    repeat: bool = True

    @model_validator(mode='after')
    def interval(self):
        if self.start_time.tzinfo or self.end_time.tzinfo or self.end_time<=self.start_time:
            raise ValueError('Informe horários locais com término após o início.')
        return self


@router.get('/schedule')
async def list_schedule(request: Request):
    user=await account(request); return await get_schedules(user['user_id'])


@router.post('/schedule')
async def create_schedule(request: Request,body: ScheduleBody):
    async def apply(session,user):
        book=await catalog.owned(session,Notebook,user.id,body.notebook_id)
        row=StudySchedule(user_id=user.id,**body.model_dump()); session.add(row); await session.flush()
        return schedule_json(row,book)
    return await mutate(request,['study-schedule',body.model_dump(mode='json')],apply)


@router.delete('/schedule/{schedule_id}')
async def delete_schedule(request: Request,schedule_id: UUID):
    async def apply(session,user):
        row=await catalog.owned(session,StudySchedule,user.id,schedule_id)
        await session.delete(row); return {'message':'Schedule deleted'}
    return await mutate(request,['delete-study-schedule',str(schedule_id)],apply)


@router.post('/programs/{program_id}/update-disciplinas')
async def update_disciplines(request: Request,program_id: UUID,data: dict):
    async def apply(session,user):
        program=await catalog.owned(session,StudyProgram,user.id,program_id)
        updated=0
        for incoming in data.get('disciplinas',[]):
            if not incoming.get('notebook_id'): continue
            try: identity=UUID(incoming['notebook_id'])
            except (ValueError,TypeError): raise HTTPException(422,'Caderno inválido.')
            book=await catalog.owned(session,Notebook,user.id,identity)
            if book.program_id!=program.id: raise HTTPException(404,'Disciplina não pertence ao programa.')
            if 'weight' in incoming:
                weight=positive_number(incoming['weight'])
                if weight is None: raise HTTPException(422,'Informe pesos maiores que zero.')
                book.weight=weight; book.peso_status='ajustado_pelo_usuario'; book.peso_fonte=''
            for field in ('dificuldade','user_difficulty'):
                if field in incoming:
                    if incoming[field] not in ('alta','media','baixa'): raise HTTPException(422,'Dificuldade inválida.')
                    setattr(book,field,incoming[field])
            if 'name' in incoming:
                name=str(incoming['name']).strip()
                if not name: raise HTTPException(422,'Informe o nome da disciplina.')
                book.name=name[:300]
            if 'topicos' in incoming:
                if not isinstance(incoming['topicos'],list): raise HTTPException(422,'Tópicos inválidos.')
                book.syllabus={**book.syllabus,'topicos':incoming['topicos']}
                await catalog.sync_topics(session,book)
            updated+=1
        if data.get('program_name'): program.name=str(data['program_name'])[:200]
        result={'success':True,'updated':updated,'message':f'{updated} disciplinas atualizadas!'}
        if data.get('regenerate_schedule'):
            metadata=program.edital_data or {}
            hours=data.get('hours_per_day',metadata.get('hours_per_day',4)); days=data.get('days_per_week',metadata.get('days_per_week',5))
            minutes,days=settings(hours,days)
            books=await catalog.notebook_rows(session,user.id,program_id=program.id)
            ids=[book.id for book in books]
            await session.execute(delete(StudySchedule).where(StudySchedule.user_id==user.id,StudySchedule.notebook_id.in_(ids)))
            weighted=sorted(books,key=lambda b:b.weight*{'alta':1.3,'media':1,'baixa':.8}.get(b.user_difficulty,1),reverse=True)
            weekly=[]
            for day in range(days):
                if not weighted: break
                chosen=[b for i,b in enumerate(weighted) if i%days==day or (i+1)%days==day] or [weighted[day%len(weighted)]]
                total=sum(b.weight*{'alta':1.3,'media':1,'baixa':.8}.get(b.user_difficulty,1) for b in chosen)
                blocks=[]; remaining=minutes
                for book in chosen:
                    effective=book.weight*{'alta':1.3,'media':1,'baixa':.8}.get(book.user_difficulty,1)
                    duration=min(remaining,max(15,int(minutes*effective/total)//15*15))
                    if duration<=0: break
                    blocks.append({'disciplina':book.name,'duracao_minutos':duration,'tipo_estudo':'Teoria + Questões',
                        'prioridade':'alta' if book.user_difficulty=='alta' else 'media'})
                    remaining-=duration
                weekly.append({'dia':LABELS[day],'blocos':blocks})
            count=await schedules(session,user.id,books,weekly,minutes,days)
            program.edital_data={**metadata,'hours_per_day':hours,'days_per_week':days}
            result['schedules_regenerated']=count
        return result
    return await mutate(request,['update-program-disciplines',str(program_id),data],apply)


@router.get('/programs/{program_id}/study-indicators')
async def indicators(request: Request,program_id: UUID):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session:
        await catalog.owned(session,StudyProgram,uid,program_id)
        books=await catalog.notebook_rows(session,uid,program_id=program_id); ids=[b.id for b in books]
        facts=await catalog.facts(session,uid,books)
        counts={}
        for model,key in [(StudySession,'sessions_count'),(StudyNote,'notes_count')]:
            counts[key]=dict((await session.execute(select(model.notebook_id,func.count()).where(model.user_id==uid,model.notebook_id.in_(ids)).group_by(model.notebook_id))).all())
        cards=(await session.execute(select(Flashcard.notebook_id,func.count(),func.count().filter(Flashcard.next_review<=local_today(user.get('timezone') or 'America/Sao_Paulo')))
            .where(Flashcard.user_id==uid,Flashcard.archived_at.is_(None),Flashcard.notebook_id.in_(ids)).group_by(Flashcard.notebook_id))).all()
        card_totals={nid:(total,due) for nid,total,due in cards}; result=[]
        for book in books:
            value=facts[book.id]; total=value['total_questions']; correct=value['correct_questions']; minutes=value['total_study_time_minutes']
            row=catalog.public(book)
            result.append({**row,'total_questions_answered':total,'correct_questions':correct,'accuracy':round(correct/total*100,1) if total else 0,
                'total_study_minutes':minutes,'study_hours':round(minutes/60,1),'flashcards_total':card_totals.get(book.id,(0,0))[0],
                'flashcards_due':card_totals.get(book.id,(0,0))[1],'notes_count':counts['notes_count'].get(book.id,0),
                'sessions_count':counts['sessions_count'].get(book.id,0),'question_progress':min(100,round(total/max((book.num_questoes_edital or 0)*10,100)*100))})
        return {'program_id':str(program_id),'indicators':sorted(result,key=lambda r:r['weight'],reverse=True)}


@router.get("/programs/{program_id}/cronograma")
async def get_program_cronograma(request: Request, program_id: UUID, session_token: Optional[str] = Cookie(None)):
    """Get the study schedule/cronograma for a specific program"""
    auth_header = request.headers.get("Authorization")
    user = SimpleNamespace(**(await account(request)))

    program = await get_program(user.user_id,program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Programa não encontrado")

    schedules = await get_schedules(user.user_id,program_id)

    notebooks = await get_notebooks(user.user_id,program_id)

    nb_lookup = {nb["notebook_id"]: nb for nb in notebooks}

    for sched in schedules:
        nb = nb_lookup.get(sched.get("notebook_id"))
        if nb:
            sched["disciplina_nome"] = nb["name"]
            sched["disciplina_color"] = nb.get("color", "#007AFF")
            sched["weight"] = nb.get("weight", 1)
            # Include assuntos_foco if available
            if not sched.get("assuntos_foco"):
                sched["assuntos_foco"] = []

    days_order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    day_labels = {"monday": "Segunda", "tuesday": "Terça", "wednesday": "Quarta", "thursday": "Quinta", "friday": "Sexta", "saturday": "Sábado", "sunday": "Domingo"}

    cronograma_by_day = []
    for day in days_order:
        day_schedules = [s for s in schedules if s.get("day_of_week") == day]
        if day_schedules:
            day_schedules.sort(key=lambda x: x.get("start_time", "00:00"))
            total_minutes = 0
            for s in day_schedules:
                try:
                    start_parts = s.get("start_time", "00:00").split(":")
                    end_parts = s.get("end_time", "00:00").split(":")
                    start_min = int(start_parts[0]) * 60 + int(start_parts[1])
                    end_min = int(end_parts[0]) * 60 + int(end_parts[1])
                    total_minutes += (end_min - start_min)
                except (ValueError, IndexError):
                    pass
            cronograma_by_day.append({
                "day": day,
                "day_label": day_labels.get(day, day),
                "blocos": day_schedules,
                "total_minutes": total_minutes
            })

    weight_summary = []
    total_weight = sum(nb.get("weight", 1) for nb in notebooks)
    for nb in sorted(notebooks, key=lambda x: x.get("weight", 1), reverse=True):
        w = nb.get("weight", 1)
        weight_summary.append({
            "disciplina": nb["name"],
            "peso": w,
            "percentual": round((w / total_weight * 100) if total_weight > 0 else 0, 1),
            "num_questoes": nb.get("num_questoes_edital", 0),
            "dificuldade": nb.get("dificuldade", "media"),
            "color": nb.get("color", "#007AFF"),
            "topicos": nb.get("topicos", []),
            "conteudo_programatico": nb.get("conteudo_programatico", [])
        })

    return {
        "program": program,
        "cronograma": cronograma_by_day,
        "disciplinas": weight_summary,
        "notebooks": notebooks,
        "estrategia": program.get("edital_data", {}).get("estrategia", {}),
        "total_schedules": len(schedules)
    }


@router.get("/programs/{program_id}/edital-verticalizado")
async def get_edital_verticalizado(request: Request, program_id: UUID, session_token: Optional[str] = Cookie(None)):
    """Generate a verticalized edital view - organized list of all disciplines and their detailed content/topics"""
    auth_header = request.headers.get("Authorization")
    user = SimpleNamespace(**(await account(request)))

    program = await get_program(user.user_id,program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Programa não encontrado")

    notebooks = await get_notebooks(user.user_id,program_id)

    concurso_info = program.get("edital_data", {}).get("concurso", {})
    cargo_info = program.get("edital_data", {}).get("cargo_selecionado", {})

    # Build verticalized view
    disciplinas_verticalizadas = []
    total_assuntos = 0

    from study_resources import normalize_content, prioritize
    progress_by_notebook = await get_progress(user.user_id,[nb['notebook_id'] for nb in notebooks])

    for nb in notebooks:
        conteudo = normalize_content(nb.get("conteudo_programatico"), nb.get("topicos", []), preserve_keys=True)
        topicos = nb.get("topicos", [])

        # Count total assuntos
        assuntos_count = len(conteudo)
        subtopicos_count = sum(len(item.get("subtopicos", [])) for item in conteudo)
        total_assuntos += assuntos_count + subtopicos_count

        disc_entry = {
            "notebook_id": nb.get("notebook_id"),
            "topic_progress": progress_by_notebook.get(nb.get("notebook_id"), {}),
            "nome": nb.get("name", ""),
            "peso": nb.get("weight", 1),
            "num_questoes": nb.get("num_questoes_edital", 0),
            "peso_fonte": nb.get("peso_fonte", ""),
            "peso_status": nb.get("peso_status", "a_conferir"),
            "num_questoes_fonte": nb.get("num_questoes_fonte", ""),
            "num_questoes_status": nb.get("num_questoes_status", "a_conferir"),
            "dificuldade": nb.get("dificuldade", "media"),
            "grupo": nb.get("grupo", ""),
            "color": nb.get("color", "#007AFF"),
            "topicos": topicos,
            "conteudo_programatico": conteudo,
            "fontes": nb.get("fontes", []),
            "total_assuntos": assuntos_count,
            "total_subtopicos": subtopicos_count,
            "study_hours": round(nb.get("total_study_time_minutes", 0) / 60, 1),
            "total_questions_answered": nb.get("total_questions", 0),
            "accuracy": round((nb.get("correct_questions", 0) / nb.get("total_questions", 1) * 100) if nb.get("total_questions", 0) > 0 else 0, 1)
        }
        disciplinas_verticalizadas.append(disc_entry)

    return {
        "success": True,
        "program_id": program_id,
        "program_name": program.get("name", ""),
        "concurso": concurso_info,
        "cargo": cargo_info.get("nome", concurso_info.get("cargo", "")),
        "banca": concurso_info.get("banca", ""),
        "orgao": concurso_info.get("orgao", ""),
        "target_date": program.get("target_date"),
        "total_disciplinas": len(disciplinas_verticalizadas),
        "total_assuntos": total_assuntos,
        "disciplinas": prioritize(disciplinas_verticalizadas)
    }

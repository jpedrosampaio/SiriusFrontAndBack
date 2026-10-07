"""Atomic edital imports; each subject/topic/schedule is a relational row."""
from datetime import date,time
from uuid import UUID
from fastapi import HTTPException
from db.activity import run_activity
from db.models.studies import StudyArea,StudyProgram,StudyTarget,Notebook,StudySchedule
from db.models.files import EditalAnalysis
from db.session import unit_of_work
from services.studies_catalog import owned,public,sync_topics
from services.planning import apply_xp
from study_resources import positive_number,normalize_content

DAYS=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
LABELS=['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']
COLORS=['#007AFF','#34C759','#FF9500','#FF3B30','#AF52DE','#5AC8FA','#FF2D55','#FFCC00']


def settings(hours,days):
    value=positive_number(hours)
    if value is None or not .25<=value<=12 or type(days) is not int or not 1<=days<=7:
        raise HTTPException(422,'Informe entre 0,25 e 12 horas por dia e 1 a 7 dias por semana.')
    return int(value*60),days


def exam_date(value,strict=True):
    if not value: return None
    try: return date.fromisoformat(value)
    except (ValueError,TypeError):
        if strict: raise HTTPException(422,'Data inválida; use AAAA-MM-DD.')
        return None


async def validate_area(user_id,area_id,hours,days,target_date):
    settings(hours,days); exam_date(target_date)
    try: uid,aid=UUID(str(user_id)),UUID(str(area_id))
    except ValueError: raise HTTPException(422,'Área inválida.')
    async with unit_of_work() as session: await owned(session,StudyArea,uid,aid)


async def schedules(session,user_id,notebooks,weekly,minutes,days):
    count=0; used={}
    by_name={book.name.casefold():book for book in notebooks}
    for entry in weekly:
        label=entry.get('dia',''); day=dict(zip(LABELS,DAYS)).get(label,str(label).lower())
        if day not in DAYS: raise HTTPException(422,'A IA retornou um dia de cronograma inválido.')
        if day not in used and len(used)>=days: raise HTTPException(422,'Cronograma excede os dias disponíveis.')
        for block in entry.get('blocos',[]):
            name=str(block.get('disciplina','')).casefold()
            book=by_name.get(name)
            if not book: continue  # Generic revision blocks have no subject, as in the existing contract.
            duration=block.get('duracao_minutos',60)
            if type(duration) is not int or duration<=0 or used.get(day,0)+duration>minutes:
                raise HTTPException(422,'Cronograma excede o tempo diário ou contém duração inválida.')
            start=480+used.get(day,0); end=start+duration
            session.add(StudySchedule(user_id=user_id,notebook_id=book.id,day_of_week=day,
                start_time=time(start//60,start%60),end_time=time(end//60,end%60),repeat=True,
                tipo_estudo=str(block.get('tipo_estudo','Teoria + Questões')),prioridade=str(block.get('prioridade','media')),
                assuntos_foco=[str(v) for v in block.get('assuntos_foco',[])][:100]))
            used[day]=used.get(day,0)+duration; count+=1
    return count


async def create(user_id,key,fingerprint,*,area_id,target_date,hours,days,concurso,disciplines,weekly,strategy,filename,cargo=None,analysis_id=None):
    minutes,days=settings(hours,days)
    if not isinstance(disciplines,list) or not disciplines: raise HTTPException(422,'Disciplinas não encontradas.')
    if len(disciplines)>100: raise HTTPException(422,'Máximo de 100 disciplinas por programa.')
    async def apply(session,user):
        area=await owned(session,StudyArea,user.id,UUID(area_id))
        if analysis_id: await owned(session,EditalAnalysis,user.id,UUID(analysis_id))
        name=concurso.get('nome') or 'Programa do Concurso'
        if concurso.get('cargo'): name+=f" - {concurso['cargo']}"
        metadata={'concurso':concurso,'estrategia':strategy,'total_disciplinas':len(disciplines),
            'hours_per_day':hours,'days_per_week':days,'pdf_filename':filename}
        if cargo: metadata['cargo_selecionado']=cargo
        if analysis_id: metadata['analysis_id']=analysis_id
        program=StudyProgram(user_id=user.id,area_id=area.id,name=name[:100],
            description=f"Banca: {concurso.get('banca','N/A')} | Órgão: {concurso.get('orgao','N/A')}",
            color='#8B5CF6',icon='file-text',target_date=exam_date(target_date) or exam_date(concurso.get('data_prova'),False),
            source_type='edital_import',edital_data=metadata)
        session.add(program); await session.flush()
        session.add(StudyTarget(user_id=user.id,program_id=program.id,kind='contest',name=program.name,exam_date=program.target_date,
            institution=concurso.get('orgao'),board=concurso.get('banca'),position=concurso.get('cargo'),metadata_origin='edital'))
        books=[]
        for index,disc in enumerate(disciplines):
            resources=disc.get('recursos_recomendados') or []
            if isinstance(resources,str): resources=[resources]
            topicos=[str(t) for t in disc.get('topicos',[])]
            book=Notebook(user_id=user.id,area_id=area.id,program_id=program.id,name=str(disc.get('nome') or f'Disciplina {index+1}'),
                description=str(disc.get('dicas_estudo') or disc.get('grupo') or ''),color=COLORS[index%len(COLORS)],tags=topicos[:10],
                weight=positive_number(disc.get('peso')) or 1,dificuldade=str(disc.get('dificuldade') or 'media'),
                num_questoes_edital=max(0,int(disc.get('num_questoes') or 0)),recursos_recomendados=resources,
                syllabus={'topicos':topicos,'conteudo_programatico':normalize_content(disc.get('conteudo_programatico'),topicos,preserve_keys=True)},
                fontes=disc.get('fontes') or [],grupo=str(disc.get('grupo') or ''),
                **{field:str(disc.get(field) or ('a_conferir' if field.endswith('_status') else ''))
                    for field in ('peso_fonte','peso_status','num_questoes_fonte','num_questoes_status')})
            session.add(book); await session.flush(); await sync_topics(session,book); books.append(book)
        count=await schedules(session,user.id,books,weekly,minutes,days)
        apply_xp(user,25)
        await session.flush()
        return {'success':True,'program':public(program),'concurso':concurso,'cargo':cargo,
            'disciplinas':[public(b) for b in books],'cronograma':weekly,'estrategia':strategy,
            'schedules_created':count,'xp_earned':25,'message':f'Programa criado com {len(books)} disciplinas e {count} blocos.'}
    return await run_activity(UUID(user_id),key,fingerprint,apply)

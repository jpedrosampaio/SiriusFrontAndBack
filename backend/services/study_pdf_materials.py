"""Persist all generated PDF study materials in one activity transaction."""
import hashlib
from uuid import UUID
from fastapi import APIRouter,Request,UploadFile,File,Form,HTTPException
from db.activity import run_activity
from db.session import unit_of_work
from db.models.studies import Notebook,StudyNote,Flashcard
from services.auth_routes import account
from services.studies_catalog import owned,public
from services.planning import apply_xp
from services.time import local_today
from services import study_material_routes as material,study_cards,exam_catalog,study_quizzes
from services.study_material_prompts import pdf_prompt

router=APIRouter(prefix='/study/content')


def strings(value):
    if not isinstance(value,list) or any(not isinstance(item,str) for item in value):
        raise HTTPException(502,'A IA retornou uma lista de conteúdo inválida.')
    return value


@router.post('/analyze-pdf')
async def analyze(request: Request,file: UploadFile=File(...),notebook_id: UUID=Form(...),
                  generate_notes: bool=Form(True),generate_flashcards: bool=Form(True),generate_quiz: bool=Form(True),
                  num_flashcards: int=Form(10,ge=1,le=100),num_quiz_questions: int=Form(5,ge=1,le=100)):
    user=await account(request); uid=UUID(user['user_id'])
    async with unit_of_work() as session: await owned(session,Notebook,uid,notebook_id)
    if not (file.filename or '').lower().endswith('.pdf'): raise HTTPException(400,'Apenas arquivos PDF são aceitos.')
    if not any((generate_notes,generate_flashcards,generate_quiz)): raise HTTPException(422,'Selecione ao menos um material para gerar.')
    if not await material._key(user['user_id']): raise HTTPException(503,'Serviço de IA indisponível. Configure sua chave no perfil.')
    content=await material.read_upload(file)
    part=await material.upload_part(content,file.filename,'application/pdf',user['user_id'])
    parsed=await material.generate(user['user_id'],pdf_prompt(generate_notes,generate_flashcards,generate_quiz,num_flashcards,num_quiz_questions),
        [part,'Analise este documento de estudo e gere materiais de revisão completos em JSON:'],'assistant_chat')
    review=None; cards=[]; quiz=None
    if generate_notes:
        review=parsed.get('review_notes')
        if not isinstance(review,dict) or not isinstance(review.get('summary'),str) or not review['summary'].strip():
            raise HTTPException(502,'A IA não retornou a revisão solicitada.')
        title=review.get('title') or file.filename
        if not isinstance(title,str): raise HTTPException(502,'Título de revisão inválido.')
        text=f"# {title}\n\n{review['summary']}\n\n"
        important=strings(review.get('important_points',[])); tips=strings(review.get('study_tips',[]))
        if important: text+='## Pontos Importantes\n'+'\n'.join(f'• {p}' for p in important)+'\n\n'
        if tips: text+='## Dicas de Estudo\n'+'\n'.join(f'• {t}' for t in tips)+'\n'
        review={'title':f'📝 Revisão: {title}','content':text,'tags':strings(review.get('key_topics',[]))[:10]}
    if generate_flashcards:
        cards=parsed.get('flashcards')
        if not isinstance(cards,list) or len(cards)!=num_flashcards: raise HTTPException(502,'A IA não retornou a quantidade solicitada de cartões.')
        for card in cards:
            if not isinstance(card,dict) or any(not isinstance(card.get(k),str) or not card[k].strip() for k in ('front','back')):
                raise HTTPException(502,'A IA retornou cartão incompleto.')
            if card.get('deck_name') is not None and not isinstance(card['deck_name'],str): raise HTTPException(502,'Nome de baralho inválido.')
    if generate_quiz:
        quiz=parsed.get('quiz')
        if not isinstance(quiz,dict) or not isinstance(quiz.get('questions'),list) or len(quiz['questions'])!=num_quiz_questions:
            raise HTTPException(502,'A IA não retornou a quantidade solicitada de questões.')
        for question in quiz['questions']:
            if not isinstance(question,dict) or not isinstance(question.get('question_text'),str) or not question['question_text'].strip() or not question.get('correct_answer'):
                raise HTTPException(502,'A IA retornou uma questão incompleta.')
            strings(question.get('options'))
        if quiz.get('title') is not None and not isinstance(quiz['title'],str): raise HTTPException(502,'Título do quiz inválido.')
    async def apply(session,owner):
        await owned(session,Notebook,owner.id,notebook_id)
        result={'filename':file.filename,'notebook_id':str(notebook_id)}; xp=0; generated=[]
        if review:
            note=StudyNote(user_id=owner.id,notebook_id=notebook_id,**review,links=[],ai_generated=True,source_pdf=file.filename)
            session.add(note); await session.flush(); result['note']=public(note); xp+=5; generated.append('revisão')
        if cards:
            rows=[Flashcard(user_id=owner.id,notebook_id=notebook_id,front=c['front'],back=c['back'],deck_name=c.get('deck_name') or 'PDF Import',
                ai_generated=True,source_pdf=file.filename,interval_days=0,next_review=local_today(owner.timezone)) for c in cards]
            session.add_all(rows); await session.flush(); result['flashcards']=[study_cards.public(c) for c in rows]
            result['flashcards_count']=len(rows); xp+=len(rows); generated.append(f'{len(rows)} flashcards')
        if quiz:
            document={'title':quiz.get('title') or f'Quiz: {file.filename}','notebook_id':str(notebook_id),'source_type':'ai_generated','pdf_filename':file.filename}
            saved=await exam_catalog.create_in_session(session,owner,document,quiz['questions'],kind='quiz')
            result['quiz']={**study_quizzes.quiz_json(saved['simulado']),'source_pdf':file.filename}; xp+=5; generated.append('quiz')
        apply_xp(owner,xp)
        return {**result,'xp_earned':xp,'success':True,'message':f"Conteúdo analisado! Gerado: {', '.join(generated)}. +{xp} XP"}
    return await run_activity(uid,request.headers.get('Idempotency-Key'),['pdf-materials',str(notebook_id),file.filename,
        hashlib.sha256(content).hexdigest(),generate_notes,generate_flashcards,generate_quiz,num_flashcards,num_quiz_questions],apply)

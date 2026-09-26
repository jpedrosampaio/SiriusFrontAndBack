# Frozen main 8b9424d oracle, used only in regression comparisons.
from datetime import datetime, timedelta, timezone
from fastapi import Request, Cookie
from typing import Optional
async def get_analytics_data(request: Request, days: int = 7, session_token: Optional[str] = Cookie(None)):
    """Get historical analytics data for dashboard charts"""
    auth_header = request.headers.get("Authorization")
    user = await get_current_user(authorization=auth_header, session_token=session_token)
    
    if days > 90:
        days = 90
    
    # Generate date range
    today = datetime.now(timezone.utc)
    date_range = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days - 1, -1, -1)]
    
    # Fetch all required data in parallel
    habits = await db.habits.find({"user_id": user.user_id}, {"_id": 0}).to_list(1000)
    
    # Task instances for date range
    task_instances = await db.task_instances.find({
        "user_id": user.user_id,
        "date": {"$gte": date_range[0], "$lte": date_range[-1]}
    }, {"_id": 0}).to_list(5000)
    
    # Transactions for date range
    transactions = await db.transactions.find({
        "user_id": user.user_id,
        "date": {"$gte": date_range[0], "$lte": date_range[-1]}
    }, {"_id": 0}).to_list(5000)
    
    # Study sessions
    study_sessions = await db.study_sessions.find({
        "user_id": user.user_id,
        "date": {"$gte": date_range[0], "$lte": date_range[-1]}
    }, {"_id": 0}).to_list(5000)
    
    # Workout logs
    workout_logs = await db.workout_logs.find({
        "user_id": user.user_id,
        "date": {"$gte": date_range[0], "$lte": date_range[-1]},
        "completed": True
    }, {"_id": 0}).to_list(1000)
    
    # Question logs
    question_logs = await db.question_logs.find({
        "user_id": user.user_id,
        "date": {"$gte": date_range[0], "$lte": date_range[-1]}
    }, {"_id": 0}).to_list(5000)
    
    # XP history from various collections
    xp_logs = await db.xp_logs.find({
        "user_id": user.user_id,
        "date": {"$gte": date_range[0], "$lte": date_range[-1]}
    }, {"_id": 0}).to_list(5000)
    
    # Build daily data
    daily_data = []
    cumulative_xp = 0
    
    for date in date_range:
        day_label = date[5:]  # MM-DD format
        
        # Tasks
        tasks_done = len([t for t in task_instances if t.get("date") == date and t.get("completed")])
        
        # Habits
        habits_done = len([h for h in habits if date in h.get("completions", [])])
        habits_total = len(habits)
        
        # Finance
        day_income = sum(t["amount"] for t in transactions if t.get("date") == date and t.get("type") == "income")
        day_expenses = sum(t["amount"] for t in transactions if t.get("date") == date and t.get("type") == "expense")
        
        # Study
        study_minutes = sum(s.get("duration_minutes", 0) for s in study_sessions if s.get("date") == date)
        
        # Workouts
        workouts_done = len([w for w in workout_logs if w.get("date") == date])
        workout_minutes = sum(w.get("duration_minutes", 0) for w in workout_logs if w.get("date") == date)
        
        # Questions
        questions_answered = sum(q.get("total", 0) for q in question_logs if q.get("date") == date)
        questions_correct = sum(q.get("correct", 0) for q in question_logs if q.get("date") == date)
        
        # XP
        day_xp = sum(x.get("amount", 0) for x in xp_logs if x.get("date") == date)
        cumulative_xp += day_xp
        
        daily_data.append({
            "date": date,
            "label": day_label,
            "tasks": tasks_done,
            "habits": habits_done,
            "habits_total": habits_total,
            "income": round(day_income, 2),
            "expenses": round(day_expenses, 2),
            "balance": round(day_income - day_expenses, 2),
            "study_min": study_minutes,
            "workouts": workouts_done,
            "workout_min": workout_minutes,
            "questions": questions_answered,
            "correct": questions_correct,
            "xp": day_xp,
            "xp_cumulative": cumulative_xp,
        })
    
    return {
        "days": days,
        "data": daily_data,
        "totals": {
            "tasks": sum(d["tasks"] for d in daily_data),
            "habits_avg": round(sum(d["habits"] for d in daily_data) / max(len(daily_data), 1), 1),
            "income": round(sum(d["income"] for d in daily_data), 2),
            "expenses": round(sum(d["expenses"] for d in daily_data), 2),
            "study_hours": round(sum(d["study_min"] for d in daily_data) / 60, 1),
            "workouts": sum(d["workouts"] for d in daily_data),
            "questions": sum(d["questions"] for d in daily_data),
            "xp_earned": sum(d["xp"] for d in daily_data),
        }
    }

import logging
async def build_ai_system_prompt(user_id: str, page: str = "", page_context: str = "") -> str:
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d/%m/%Y")
    time_str = now.strftime("%H:%M")

    lines = [f"Você é o assistente integrado do Sirius, um aplicativo completo de gestão pessoal.",
             f"Hoje é {date_str} e são {time_str} UTC.",
             f"",
             f"## Módulos do Sirius",
             f"- **Treinos**: planos de treino, exercícios, séries, cargas, RPE, histórico",
             f"- **Nutrição**: refeições, alimentos, calorias, macros, planejamento alimentar",
             f"- **Estudos**: matérias, tópicos, flashcards, sessões de estudo, provas, redação",
             f"- **Finanças**: receitas, despesas, orçamentos, projeções, categorias",
             f"- **Tarefas**: tarefas diárias, hábitos, tracker, gamificação (XP, ranking)",
             f"- **Metas**: objetivos de curto/médio/longo prazo com progresso",
             f"- **Calendário**: eventos, agendamentos",
             f"- **Dashboard**: visão geral de todas as áreas",
             f"",
             f"## Comportamento",
             f"- Responda de forma objetiva e prática em português.",
             f"- Use emojis com moderação para tornar a resposta mais amigável.",
             f"- Sempre que relevante, sugira ações concretas que o usuário pode fazer no app.",
             f"- Se o usuário pedir algo que você não pode fazer diretamente (criar/editar dados),",
             f"  explique claramente o que ele precisa fazer e em qual seção do app."]

    try:
        user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password": 0, "gemini_api_key": 0, "email": 0})
        if user_doc:
            name = user_doc.get("name", "")
            if name:
                lines.append(f"")
                lines.append(f"## Dados do usuário")
                lines.append(f"- Nome: {name}")
                rank = user_doc.get("rank", "")
                xp = user_doc.get("xp", 0)
                if rank:
                    lines.append(f"- Rank: {rank} | XP: {xp}")

            # Fetch summaries from each module
            today = now.strftime("%Y-%m-%d")
            current_month = now.strftime("%Y-%m")

            # Tasks today
            tasks_today = await db.task_instances.count_documents({"user_id": user_id, "date": today})
            tasks_done = await db.task_instances.count_documents({"user_id": user_id, "date": today, "completed": True})
            if tasks_today > 0:
                lines.append(f"- Tarefas hoje: {tasks_done}/{tasks_today} concluídas")

            # Habits
            habits_count = await db.habits.count_documents({"user_id": user_id})
            if habits_count > 0:
                lines.append(f"- Hábitos cadastrados: {habits_count}")

            # Workouts this month
            workouts_month = await db.workout_logs.count_documents({"user_id": user_id, "date": {"$regex": f"^{current_month}"}})
            if workouts_month > 0:
                lines.append(f"- Treinos no mês: {workouts_month}")

            # Finance summary (current month)
            income = await db.transactions.aggregate([
                {"$match": {"user_id": user_id, "type": "receita", "date": {"$regex": f"^{current_month}"}}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]).to_list(1)
            expenses = await db.transactions.aggregate([
                {"$match": {"user_id": user_id, "type": "despesa", "date": {"$regex": f"^{current_month}"}}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]).to_list(1)
            inc_total = income[0]["total"] if income else 0
            exp_total = expenses[0]["total"] if expenses else 0
            if inc_total or exp_total:
                lines.append(f"- Finanças do mês: R$ {inc_total:.2f} receitas | R$ {exp_total:.2f} despesas")

            # Goals
            goals_count = await db.goals.count_documents({"user_id": user_id})
            if goals_count > 0:
                lines.append(f"- Metas cadastradas: {goals_count}")

            # Study
            study_hours = await db.study_sessions.aggregate([
                {"$match": {"user_id": user_id, "date": {"$regex": f"^{current_month}"}}},
                {"$group": {"_id": None, "total": {"$sum": "$duration_minutes"}}}
            ]).to_list(1)
            total_minutes = study_hours[0]["total"] if study_hours else 0
            if total_minutes > 0:
                lines.append(f"- Estudos no mês: {total_minutes} minutos")

    except Exception as e:
        logging.warning(f"Failed to build AI context: {e}")

    if page:
        page_map = {
            "/dashboard": "Dashboard - visão geral do app",
            "/treinos": "Treinos - planos e histórico de treinos",
            "/nutricao": "Nutrição - refeições e alimentos",
            "/nutrição": "Nutrição - refeições e alimentos",
            "/estudos": "Estudos - matérias e sessões de estudo",
            "/financas": "Finanças - receitas, despesas e orçamentos",
            "/finanças": "Finanças - receitas, despesas e orçamentos",
            "/tarefas": "Tarefas e hábitos",
            "/metas": "Metas e objetivos",
            "/calendario": "Calendário de eventos",
            "/calendário": "Calendário de eventos",
            "/perfil": "Perfil do usuário e configurações",
        }
        page_name = page_map.get(page, f"Página: {page}")
        lines.append(f"")
        lines.append(f"## Contexto atual")
        lines.append(f"O usuário está na página: {page_name}")
        if page_context:
            lines.append(f"Contexto adicional: {page_context}")

    return "\n".join(lines)

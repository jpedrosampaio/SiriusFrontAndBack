"""Validate AI calendars before saving; never silently shorten a requested plan."""
import copy
import re


def calendar_shape(request):
    if request.generation_mode == "tipo_treino" and request.workout_type != "corrida":
        return request.cycle_weeks or 4, request.training_days_per_week or 5
    weeks = {"dia": 1, "semana": 1, "mes": 4, "ciclo": 10}.get(request.duration)
    if weeks is None:
        raise ValueError("Duração de treino inválida.")
    frequency = (request.weekly_frequency or 4) if request.workout_type == "corrida" else 5
    return weeks, 1 if request.duration == "dia" else frequency


def validate_ai_calendar(data, request):
    if not isinstance(data, dict):
        raise ValueError("A resposta deve ser um objeto JSON.")
    weeks, frequency = calendar_shape(request)
    progression = data.get("weekly_progression") or []
    if not isinstance(progression, list):
        raise ValueError("weekly_progression deve ser uma lista.")
    seen_weeks = set()
    for item in progression:
        if not isinstance(item, dict) or not str(item.get("week", "")).isdigit():
            raise ValueError("A progressão deve indicar a semana como número inteiro.")
        item["week"] = int(item["week"])
        if not 1 <= item["week"] <= weeks or item["week"] in seen_weeks:
            raise ValueError("A progressão contém semanas repetidas ou fora do calendário.")
        seen_weeks.add(item["week"])
    data["weekly_progression"] = progression
    split_mode = request.generation_mode == "tipo_treino" and request.workout_type != "corrida"
    if split_mode:
        splits = data.get("splits")
        if not isinstance(splits, list) or not splits:
            raise ValueError("Retorne os modelos em splits; não substitua por days incompletos.")
        expected = {str(s.get("label", "")).lower() for s in (request.split_config or [])}
        actual = {str(s.get("split_label", "")).lower() for s in splits if isinstance(s, dict)}
        if not expected or not expected.issubset(actual) or not (actual - {"cardio", "descanso", ""}):
            raise ValueError("Faltam divisões de treino solicitadas em splits.")
        entries = splits
    else:
        entries = data.get("days")
        if not isinstance(entries, list) or len(entries) != weeks * frequency:
            raise ValueError(f"Retorne exatamente {weeks * frequency} dias: {weeks} semanas de {frequency} dias.")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("exercises"), list) or not entry["exercises"]:
            raise ValueError("Cada dia ou divisão precisa conter exercícios.")
        if any(not isinstance(ex, dict) or not ex.get("name") for ex in entry["exercises"]):
            raise ValueError("Há exercícios sem nome ou inválidos.")
    if not split_mode:
        data["days"] = normalize_days(entries, weeks, frequency)
    return data


def normalize_days(days, weeks, frequency):
    if len(days) != weeks * frequency:
        raise ValueError("O calendário gerado não corresponde à duração solicitada.")
    normalized = [copy.deepcopy(day) for day in days]
    for index, day in enumerate(normalized):
        week, weekday = index // frequency + 1, index % frequency + 1
        name = str(day.get("day_name", ""))
        label = str(day.get("day_label", ""))
        named = re.search(r"sem(?:ana)?[_\s]*(\d+)", name, re.I)
        labeled = re.search(r"semana\s*(\d+)", label, re.I)
        for reported in (day.get("week"), named.group(1) if named else None, labeled.group(1) if labeled else None):
            if reported is not None and str(reported) != str(week):
                raise ValueError(f"Numeração inconsistente: o dia {index + 1} deve pertencer à semana {week}.")
        day["week"] = week
        day["day_name"] = f"sem{week}_dia{weekday}"
        if not labeled:
            day["day_label"] = f"Semana {week} - Dia {weekday}" + (f": {label}" if label else "")
    return normalized


def expand_splits(plan_data, gen_data):
    days = []
    weekly_progression = plan_data.get("weekly_progression", [])
    splits = plan_data["splits"]
    split_labels_ai = [s.get("split_label", f"S{i}") for i, s in enumerate(splits)]
    days_per_week = gen_data.training_days_per_week or 5
    cycle_weeks_count = gen_data.cycle_weeks or 4

    # Build rotation pattern using split labels from AI response
    # Filter out cardio and rest splits for the main rotation
    main_splits = [s for s in splits if s.get("split_label", "").lower() not in ("cardio", "descanso")]
    cardio_split = next((s for s in splits if s.get("split_label", "").lower() == "cardio"), None)
    rest_split = next((s for s in splits if s.get("split_label", "").lower() == "descanso"), None)

    muscle_day_counter = 0
    cardio_mode = gen_data.cardio_mode or "hibrido"

    for week in range(1, cycle_weeks_count + 1):
        week_progression = next((wp for wp in weekly_progression if wp.get("week") == week), None)
        progression_note = week_progression.get("notes", "") if week_progression else ""
        progression_focus = week_progression.get("focus", "") if week_progression else ""

        for day_in_week in range(1, days_per_week + 1):
            is_rest_day = False
            is_cardio_day = False

            if cardio_mode == "hibrido_alternado" and gen_data.include_cardio and cardio_split:
                # Pattern: Muscle, Cardio, Muscle, Cardio, ..., Rest (last day)
                if day_in_week == days_per_week:
                    is_rest_day = True
                elif day_in_week % 2 == 0:
                    is_cardio_day = True
                # Odd days (1, 3, 5, ...) are muscle days
            elif cardio_mode == "hibrido" and gen_data.include_cardio:
                # Hybrid mode: last day is rest, all others are muscle+cardio
                if day_in_week == days_per_week:
                    is_rest_day = True

            if is_rest_day:
                if rest_split:
                    current_split = rest_split
                else:
                    current_split = {"exercises": [{"name": "Descanso ativo - Caminhada leve", "sets": 1, "reps": "20-30min", "rest_seconds": 0, "muscle_group": "descanso", "tutorial": "Caminhada leve para recuperação ativa. Mantenha ritmo tranquilo."}]}
                label = "Descanso"
                split_name = "Descanso / Recuperação"
            elif is_cardio_day and cardio_split:
                current_split = cardio_split
                label = "Cardio"
                split_name = cardio_split.get("split_name", "Cardio")
            else:
                split_idx = muscle_day_counter % len(main_splits) if main_splits else 0
                current_split = main_splits[split_idx] if main_splits else {"exercises": []}
                label = current_split.get("split_label", "?")
                split_name = current_split.get("split_name", "")
                muscle_day_counter += 1

            day_label = f"Semana {week} - Dia {day_in_week}: Treino {label} - {split_name}"

            days.append({
                "day_name": f"sem{week}_dia{day_in_week}",
                "day_label": day_label,
                "split_label": label,
                "week": week,
                "exercises": current_split.get("exercises", []),
                "progression_focus": progression_focus,
                "progression_notes": progression_note,
            })
    return days

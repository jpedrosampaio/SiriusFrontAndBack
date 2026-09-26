# AI migration map

All listed legacy call sites delegate to the central capability router. Provider transports live only in `backend/ai/providers`.

| Caller | Compatibility function | Task |
|---|---|---|
| `send_chat_message` | `call_llm` | `assistant_chat` |
| `send_chat_message` | `call_llm` | `assistant_chat` |
| `send_chat_message` | `call_llm` | `assistant_chat` |
| `send_chat_message` | `call_llm` | `assistant_chat` |
| `send_chat_message` | `call_llm` | `assistant_chat` |
| `send_chat_message` | `call_llm` | `assistant_chat` |
| `analyze_image_for_expenses` | `request_gemini` | `image_analysis` |
| `analyze_image_for_expenses` | `request_gemini` | `image_analysis` |
| `generate_report` | `call_llm` | `report_analysis` |
| `get_projection_insights` | `call_llm` | `assistant_chat` |
| `get_ai_workout_suggestions` | `call_llm` | `workout_generation` |
| `generate_workout_plan` | `call_llm` | `workout_generation` |
| `improve_workout_plan` | `call_llm` | `workout_generation` |
| `analyze_pdf_measurement` | `request_gemini` | `assistant_chat` |
| `get_workout_recommendations` | `call_llm` | `workout_generation` |
| `get_motivational_quote` | `call_llm` | `assistant_chat` |
| `estimate_food_nutrition` | `call_llm` | `nutrition_generation` |
| `estimate_foods_batch` | `call_llm` | `assistant_chat` |
| `suggest_recipe` | `request_gemini` | `nutrition_generation` |
| `import_meal_plan` | `request_gemini` | `nutrition_generation` |
| `study_ai_chat` | `call_llm` | `study_explanation` |
| `generate_flashcards` | `call_llm` | `study_explanation` |
| `generate_quiz` | `call_llm` | `study_question_generation` |
| `get_ai_study_suggestions` | `call_llm` | `study_explanation` |
| `analyze_content_pdf` | `request_gemini` | `assistant_chat` |
| `import_simulado_pdf` | `request_gemini` | `study_question_generation` |
| `generate_simulado` | `request_gemini` | `study_question_generation` |
| `import_edital_with_cargo` | `call_llm` | `edital_extract` |
| `study_ai_chat_with_file` | `request_gemini` | `study_explanation` |
| `generate_mindmap` | `request_gemini` | `mindmap_generation` |
| `correct_essay` | `request_gemini` | `assistant_chat` |
| `random_essay_theme` | `call_llm` | `assistant_chat` |
| `import_workout_plan` | `request_gemini` | `workout_generation` |
| `generate_meal_plan` | `request_gemini` | `nutrition_generation` |
| `get_daily_summary` | `call_llm` | `assistant_chat` |
| `handle_telegram_message` | `call_llm` | `assistant_chat` |
| `handle_telegram_message` | `call_llm` | `assistant_chat` |
| `handle_telegram_message` | `call_llm` | `assistant_chat` |

Edital chat uses owned lexical retrieval and actual conversation roles. TTS uses the voice capability; the interface supports browser speech. Legacy Gemini function names are compatibility facades, not separate provider transports.

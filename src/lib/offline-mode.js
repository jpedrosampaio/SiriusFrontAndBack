export const OFFLINE_MODE = process.env.REACT_APP_OFFLINE_MODE === 'true' || false;

export const OFFLINE_USER = {
  user_id: 'offline_user',
  email: 'offline@sirius.app',
  name: 'Usuário Offline',
  xp: 150,
  rank: 'Soldado',
  picture: null,
  birth_date: null,
  bio: 'Modo offline - dados de demonstração',
  gemini_api_key: null,
  created_at: '2024-01-01T00:00:00Z'
};

export const OFFLINE_DEMO_DATA = {
  tasks: [
    { task_id: 't1', user_id: 'offline_user', title: 'Exemplo de tarefa 1', description: 'Esta é uma tarefa de exemplo', completed: false, date: '2024-01-01', priority: 'medium', xp_reward: 10, recurrence: 'once', is_template: true, created_at: '2024-01-01' },
    { task_id: 't2', user_id: 'offline_user', title: 'Exemplo de tarefa 2', completed: true, date: '2024-01-01', priority: 'high', xp_reward: 15, recurrence: 'once', is_template: true, created_at: '2024-01-01' },
  ],
  habits: [
    { habit_id: 'h1', user_id: 'offline_user', name: 'Exercício físico', description: 'Treino diário', color: '#007AFF', streak: 5, best_streak: 12, completions: ['2024-01-01', '2024-01-02'], created_at: '2024-01-01' },
    { habit_id: 'h2', user_id: 'offline_user', name: 'Leitura', description: 'Ler 20 páginas', color: '#FFD700', streak: 3, best_streak: 7, completions: [], created_at: '2024-01-01' },
  ],
  transactions: [
    { transaction_id: 'tx1', user_id: 'offline_user', type: 'income', amount: 5000, category: 'salário', description: 'Salário mensal', date: '2024-01-01', created_at: '2024-01-01' },
    { transaction_id: 'tx2', user_id: 'offline_user', type: 'expense', amount: 150, category: 'alimentação', description: 'Mercado', date: '2024-01-01', created_at: '2024-01-01' },
  ],
  goals: [
    { goal_id: 'g1', user_id: 'offline_user', title: 'Economizar R$ 10.000', description: 'Fundo de emergência', target_date: '2024-12-31', progress: 35, sprint_duration: 30, daily_checks: [], sprints: [], created_at: '2024-01-01' },
  ],
  achievements: [
    { achievement_id: 'a1', user_id: 'offline_user', title: 'Primeiro Passo', description: 'Complete sua primeira tarefa', icon: 'trophy', unlocked_at: '2024-01-01' },
    { achievement_id: 'a2', user_id: 'offline_user', title: 'Consistente', description: 'Mantenha 5 dias de sequência', icon: 'flame', unlocked_at: '2024-01-01' },
  ]
};
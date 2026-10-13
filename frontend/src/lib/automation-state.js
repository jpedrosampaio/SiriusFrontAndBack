export const deliveryLabels = {
  pending: 'Aguardando envio', processing: 'Entrega em andamento', available: 'Disponível no Sirius',
  delivered: 'Recebimento confirmado', failed: 'Falha confirmada', cancelled: 'Cancelada', uncertain: 'Entrega não confirmada',
  dispatching: 'Envio iniciado', manual_retry: 'Reenvio solicitado',
};
export const eventLabels = { pending: 'Aguardando processamento', processing: 'Em processamento', processed: 'Processado', failed: 'Falha registrada' };
export const transitionTypes = ['task.completed','study.session.completed','workout.completed','expense.created','edital.updated'];
export const outcomeLabels = { resolved: 'A condição foi resolvida', cancelled: 'Ignorado pelas preferências', duplicate: 'Condição já registrada neste período', lost: 'Execução retomada' };
export function deliveryError(code) {
  return ({ simulation_only: 'Modo de simulação: mensagem não enviada.', not_paired: 'Vincule seu Telegram em Configurações.',
    disabled_by_owner: 'Regra, canal ou automações desativados nas preferências.', pairing_changed: 'O vínculo do Telegram mudou; entrega cancelada.',
    source_resolved: 'A condição do alerta foi resolvida antes do envio.', report_expired: 'Resumo antigo: envio cancelado.',
    provider_confirmation_unknown: 'O Telegram não confirmou a entrega. Reenviar pode duplicar a mensagem.',
    provider_temporarily_unavailable: 'O Telegram recusou temporariamente; consulte o estado da próxima tentativa.',
    provider_rejected: 'O Telegram recusou o envio. Verifique o vínculo antes de tentar novamente.',
    worker_interrupted_during_delivery: 'Envio interrompido. A entrega pode ter ocorrido; reenvio exige confirmação.',
    processing_failed: 'Não foi possível processar o evento. A falha permanece registrada.',
    worker_attempts_exhausted: 'Limite de tentativas atingido.', worker_disabled: 'Execução automática desativada no servidor.',
    manual_retry: 'Reenvio solicitado por você.',
  })[code] || 'Falha registrada. Consulte o suporte para revisar esta entrega.';
}
export function receiptIntent(action, identity, acceptDuplicateRisk = false) {
  return JSON.stringify({ identity, action, accept_duplicate_risk: acceptDuplicateRisk });
}

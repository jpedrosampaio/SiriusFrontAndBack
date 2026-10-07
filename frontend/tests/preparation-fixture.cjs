module.exports = {
  preparation_id:'demo', health:{status:'moderate',notice:'Indicadores operacionais, não probabilidade de aprovação.',components:[
    {key:'coverage',title:'Cobertura',value:50,reason:'1/2 assuntos marcados como estudados; contato não comprova domínio.'},
    {key:'mastery',title:'Domínio estimado',value:null,reason:'Sem questões individuais respondidas; exposição não comprova domínio.'}]},
  current_pace:{minutes_per_week:25},study_debt:{overdue_blocks:1,minutes:30},reviews_due:{topics:1,flashcards:0},
  required_pace:{minutes_per_week:60,notice:'Carga do plano registrado; não prevê conclusão do edital.'},
  candidate_model:{mean_duration_minutes:25},
  next_candidates:[{id:'topic1',notebook_id:'nb0',topic_key:'0',title:'Interpretation',discipline:'Portuguese',reasons:['revisão vencida','sem amostra de domínio']}],
  syllabus_graph:{topics:[{id:'topic1',title:'Interpretation',stage:'exposed',covered:true,mastery:{score:null,samples:0}}]},
  evidence_ledger:[{id:'session1',kind:'session',at:'2026-10-07',minutes:25,affects_mastery:false}],
  source_freshness:{computed_at:'2026-10-07'},truncated:false
};

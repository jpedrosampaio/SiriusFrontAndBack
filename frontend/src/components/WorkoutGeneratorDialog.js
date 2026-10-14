import { useEffect, useRef, useState } from 'react';
import { Sparkles, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { EQUIPMENT, MUSCLES, muscleLabel, SPLITS, splitConfig, initialGenerationForm, generationPayload, generationCount, createGenerationRequest } from '@/lib/workout-generation';
import { getApiErrorMessage } from '@/lib/api-errors';

const fieldClass = 'w-full min-w-0 min-h-[44px] rounded-xl border border-border bg-background px-3 py-2 text-sm';
function Choice({ label, value, onChange, choices }) {
  return <label className="block min-w-0 space-y-2 text-sm">{label}<select aria-label={label} className={fieldClass} value={value} onChange={e => onChange(e.target.value)}>{choices.map(([v, text]) => <option key={v} value={v}>{text}</option>)}</select></label>;
}
export default function WorkoutGeneratorDialog({ generate, onSaved }) {
  const [open, setOpen] = useState(false), [form, setForm] = useState(initialGenerationForm);
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState('');
  const requests = useRef(createGenerationRequest()), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const patch = (key, value) => setForm(previous => ({ ...previous, [key]: value }));
  const toggle = (key, value) => patch(key, (form[key] || []).includes(value) ? form[key].filter(v => v !== value) : [...(form[key] || []), value]);
  const strength = ['musculacao', 'hibrido'].includes(form.workout_type);
  const modality = { musculacao:'Musculação',calistenia:'Calistenia',corrida:'Corrida',hibrido:'Híbrido' }[form.workout_type];
  const location = { casa:'Em casa',academia:'Em academia',ar_livre:'Ao ar livre' }[form.training_location];
  const objective = { hipertrofia:'Hipertrofia',forca:'Força',condicionamento:'Condicionamento',resistencia:'Resistência',emagrecimento:'Emagrecimento',mobilidade:'Mobilidade',flexibilidade:'Flexibilidade',habilidades:'Habilidades' }[form.objective];
  const focus = form.workout_type === 'calistenia' ? { full_body:'Full Body',forca_upper:'Força superior',forca_lower:'Força inferior',condicionamento:'Condicionamento',habilidades:'Habilidades conforme o nível' }[form.calisthenics_focus]
    : form.workout_type === 'corrida' ? { condicionamento:'Condicionamento',emagrecimento:'Emagrecimento', '5km':'5 km','10km':'10 km',meia_maratona:'Meia maratona',maratona:'Maratona' }[form.running_goal]
    : form.generation_mode === 'tipo_treino' && !form.single ? `Divisão ${form.split_type}` : form.muscle_groups.length ? form.muscle_groups.map(muscleLabel).join(', ') : 'Full Body';
  async function submit(e) {
    e.preventDefault();
    let payload;
    try { payload = generationPayload(form); } catch (failure) { setError(failure.message); return; }
    const attempt = requests.current.begin(payload);
    if (!attempt) return;
    setBusy(true); setError('');
    try {
      const result = await generate(attempt.payload, attempt.key);
      if (!mounted.current) return;
      if (!result?.success) throw new Error('Resposta sem confirmação');
      requests.current.finish(); setUncertain(false); setOpen(false);
      toast.success(result.replayed ? 'Treino recuperado, sem duplicar plano ou XP.' : 'Treino gerado. Confira a proposta antes de iniciar.');
      onSaved();
    } catch (failure) {
      if (!mounted.current || failure.code === 'ERR_CANCELED') return;
      setUncertain(requests.current.finish(failure));
      setError(getApiErrorMessage(failure, 'Não foi possível confirmar o resultado. Seus campos foram preservados.'));
    } finally { if (mounted.current) setBusy(false); }
  }
  return <Dialog open={open} onOpenChange={setOpen}>
    <DialogTrigger asChild><Button data-testid="open-ai-generate-btn" className="bg-gradient-to-r from-violet-600 to-cyan-600 text-white"><Sparkles className="mr-2 h-4 w-4" />Gerar com IA</Button></DialogTrigger>
    <DialogContent className="max-w-2xl max-h-[90dvh] overflow-y-auto">
      <DialogHeader className="pr-10"><DialogTitle>Planejar meus treinos</DialogTitle><DialogDescription>Declare sua rotina e seus equipamentos. A IA propõe sessões; o Sirius organiza o calendário completo.</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="min-w-0 space-y-5">
        <fieldset disabled={busy || uncertain} className="min-w-0 space-y-5 disabled:opacity-70">
          <div className="grid min-w-0 gap-4 sm:grid-cols-2">
            <Choice label="Modalidade" value={form.workout_type} onChange={v => patch('workout_type', v)} choices={ [['musculacao','Musculação'],['calistenia','Calistenia'],['corrida','Corrida'],['hibrido','Híbrido']] } />
            <Choice label="Onde você pretende treinar?" value={form.training_location} onChange={v => patch('training_location', v)} choices={ [['','Selecione o local'],['casa','Em casa'],['academia','Em academia'],['ar_livre','Ao ar livre']] } />
            <Choice label="Objetivo" value={form.objective} onChange={v => patch('objective', v)} choices={ [['hipertrofia','Hipertrofia'],['forca','Força'],['condicionamento','Condicionamento'],['resistencia','Resistência'],['emagrecimento','Emagrecimento'],['mobilidade','Mobilidade'],['flexibilidade','Flexibilidade'],['habilidades','Habilidades']] } />
            <Choice label="Nível" value={form.level} onChange={v => patch('level', v)} choices={ [['iniciante','Iniciante'],['intermediario','Intermediário'],['avancado','Avançado']] } />
          </div>
          <section aria-label="Equipamentos disponíveis" className="space-y-3 rounded-2xl border border-border p-3">
            <h3 className="font-medium">Equipamentos disponíveis</h3><p className="text-sm text-muted-foreground">O local não presume equipamentos. Selecione apenas o que poderá usar.</p>
            <div className="flex flex-wrap gap-2"><Button type="button" variant={form.available_equipment?.length === 0 ? 'default' : 'outline'} onClick={() => patch('available_equipment', [])}>Nenhum equipamento</Button><Button type="button" variant="outline" onClick={() => patch('available_equipment', null)}>Não informado</Button></div>
            {form.training_location === 'academia' && <Button type="button" variant="outline" className="h-auto min-h-11 whitespace-normal" onClick={() => patch('available_equipment', ['halteres','barra_anilhas','banco','maquinas','polias'])}>Selecionar equipamentos comuns de academia</Button>}
            <p aria-live="polite" className="text-sm">{form.available_equipment === null ? 'Equipamentos ainda não informados.' : form.available_equipment.length === 0 ? 'Declarado: sem equipamentos.' : `${form.available_equipment.length} equipamentos selecionados; ajuste abaixo.`}</p>
            <details><summary className="min-h-11 cursor-pointer py-2 font-medium">Escolher equipamentos</summary><div className="grid gap-x-3 sm:grid-cols-2">{EQUIPMENT.map(([v, text]) => <label key={v} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={form.available_equipment?.includes(v) || false} onChange={() => toggle('available_equipment', v)} />{text}</label>)}</div></details>
          </section>
          <div className="grid gap-4 sm:grid-cols-2">
            <Choice label="Duração do planejamento" value={form.single ? 'single' : String(form.weeks)} onChange={v => setForm(p => ({ ...p, single: v === 'single', weeks: v === 'single' ? 1 : Number(v) }))} choices={ [['single','Sessão única'],['1','Uma semana'],['4','Quatro semanas'],['8','Oito semanas'],['12','Doze semanas']] } />
            {!form.single && <Choice label="Sessões por semana" value={String(form.training_days_per_week)} onChange={v => patch('training_days_per_week', Number(v))} choices={ [2,3,4,5,6,7].map(v => [String(v), `${v} sessões`]) } />}
            <label className="space-y-2 text-sm">Minutos disponíveis por sessão<input type="number" required min="10" max="180" className={fieldClass} value={form.session_minutes} onChange={e => patch('session_minutes', e.target.value)} /></label>
            {form.workout_type === 'calistenia' && <Choice label="Foco da calistenia" value={form.calisthenics_focus} onChange={v => patch('calisthenics_focus', v)} choices={ [['full_body','Full Body'],['forca_upper','Força superior'],['forca_lower','Força inferior'],['condicionamento','Condicionamento'],['habilidades','Habilidades conforme o nível']] } />}
            {form.workout_type === 'corrida' && <><Choice label="Foco da corrida" value={form.running_goal} onChange={v => patch('running_goal', v)} choices={ [['condicionamento','Condicionamento'],['5km','5 km'],['10km','10 km'],['meia_maratona','Meia maratona'],['maratona','Maratona'],['emagrecimento','Emagrecimento']] } /><Choice label="Terreno" value={form.preferred_terrain} onChange={v => patch('preferred_terrain', v)} choices={ [['asfalto','Asfalto'],['esteira','Esteira disponível'],['trilha','Trilha'],['misto','Misto']] } /></>}
            {strength && !form.single && <Choice label="Organização de força" value={form.generation_mode} onChange={v => patch('generation_mode', v)} choices={ [['periodo','Full Body / grupos selecionados'],['tipo_treino','Divisão de treinos']] } />}
          </div>
          {strength && form.generation_mode === 'tipo_treino' && !form.single ? <section className="space-y-3"><Choice label="Divisão" value={form.split_type} onChange={v => setForm(p => ({ ...p, split_type: v, split_config: splitConfig(v) }))} choices={ Object.keys(SPLITS).map(v => [v, v === 'AB' ? 'AB · superior / inferior' : v]) } />{form.split_config.map((split, i) => <details key={split.label} className="rounded-xl border p-3"><summary className="cursor-pointer break-words">{split.label} · {split.name || 'Escolha os grupos'}</summary><div className="grid sm:grid-cols-2">{MUSCLES.map(m => <label key={m} className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={split.muscle_groups.includes(m)} onChange={() => setForm(p => ({ ...p, split_config: p.split_config.map((s, j) => { if (i !== j) return s; const groups = s.muscle_groups.includes(m) ? s.muscle_groups.filter(g => g !== m) : [...s.muscle_groups, m]; return { ...s, muscle_groups: groups, name: groups.map(muscleLabel).join(', ') }; }) }))} />{muscleLabel(m)}</label>)}</div></details>)}</section> : strength && <details><summary className="min-h-11 cursor-pointer py-2">Foco muscular (opcional; vazio indica corpo todo)</summary><div className="grid sm:grid-cols-2">{MUSCLES.map(m => <label key={m} className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={form.muscle_groups.includes(m)} onChange={() => toggle('muscle_groups', m)} />{muscleLabel(m)}</label>)}</div></details>}
          {strength && <section className="space-y-3">{form.workout_type === 'musculacao' && <label className="flex min-h-11 items-center gap-2"><input type="checkbox" checked={form.include_cardio} onChange={e => patch('include_cardio', e.target.checked)} />Incluir condicionamento</label>}{(form.include_cardio || form.workout_type === 'hibrido') && <div className="grid gap-4 sm:grid-cols-2"><Choice label="Condicionamento" value={form.cardio_type} onChange={v => patch('cardio_type', v)} choices={ [['corrida','Corrida'],['bike','Bike/ciclismo'],['HIIT','HIIT'],['caminhada','Caminhada'],['natacao','Natação'],['pular_corda','Pular corda'],['eliptico','Elíptico'],['remo','Remo']] } /><Choice label="Combinação" value={form.cardio_mode} onChange={v => patch('cardio_mode', v)} choices={ [['hibrido','Força e condicionamento na sessão'],['hibrido_alternado','Alternar sessões de força e condicionamento']] } /></div>}</section>}
          <details className="rounded-xl border p-3"><summary className="min-h-11 cursor-pointer py-2">Limitações e exercícios a evitar (opcional)</summary><p className="mb-3 text-sm text-muted-foreground">Relatos pessoais não são diagnósticos. A proposta não substitui avaliação profissional. Esses campos ficam neste plano, sem copiar para o perfil.</p><label className="block space-y-2 text-sm">Condições físicas relatadas<textarea aria-label="Condições físicas relatadas" className={fieldClass} maxLength={5000} value={form.health_condition} onChange={e => patch('health_condition', e.target.value)} /></label><label className="mt-3 block space-y-2 text-sm">Exercícios a evitar, um por linha<textarea aria-label="Exercícios a evitar, um por linha" className={fieldClass} value={form.avoid_text} onChange={e => patch('avoid_text', e.target.value)} /></label></details>
        </fieldset>
        <section data-testid="generation-summary" aria-label="Resumo antes de gerar" className="space-y-2 rounded-2xl border border-primary/30 bg-primary/5 p-4 text-sm">
          <h3 className="font-semibold">Confira sua proposta</h3><p className="break-words">{modality} · {location || 'Local não informado'} · {objective} · {{ iniciante:'Iniciante',intermediario:'Intermediário',avancado:'Avançado' }[form.level]}</p><p className="break-words">Foco: {focus}</p>
          <p className="font-medium">{form.single ? 'Sessão única' : `${form.weeks} semanas × ${form.training_days_per_week} sessões por semana`} = {generationCount(form)} {generationCount(form) === 1 ? 'sessão' : 'sessões'}</p>
          <p className="break-words">Equipamentos: {form.available_equipment === null ? 'não informados' : form.available_equipment.length === 0 ? 'nenhum' : form.available_equipment.map(v => EQUIPMENT.find(([id]) => id === v)?.[1]).join(', ')}</p>
          <p>{form.session_minutes} minutos disponíveis por sessão. A duração proposta é uma estimativa.</p><p className="text-muted-foreground">Calendário completo, com variedade de sessões-base. Cargas ficam a definir; evolução depende de registros reais e da sua confirmação.</p><p className="text-muted-foreground">Proposta em semanas de sete dias, contando da criação do plano, com intervalos sem sessão. Não cria compromissos na agenda nem repete o ciclo automaticamente. Você pode ajustar a execução.</p>
        </section>
        {error && <p role="alert" className="break-words text-sm text-destructive">{error}</p>}
        {uncertain && <p role="status" className="text-sm">O resultado ainda não foi confirmado. Consulte suas fichas ou tente recuperar o mesmo pedido. A repetição usa a mesma chave e não duplica plano ou XP.</p>}
        {busy && <p role="status" className="text-sm text-muted-foreground">Gerando e validando sessões-base. Você pode fechar esta janela; os campos serão preservados.</p>}
        <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={() => setOpen(false)}>Fechar</Button><Button type="submit" data-testid="generate-ai-workout-btn" disabled={busy} className="h-auto min-h-11 flex-1 whitespace-normal">{busy && <Loader2 className="mr-2 h-4 w-4 shrink-0 animate-spin" />}{busy ? 'Gerando treino…' : uncertain ? 'Recuperar mesmo pedido' : 'Gerar treino'}</Button></div>
      </form>
    </DialogContent>
  </Dialog>;
}

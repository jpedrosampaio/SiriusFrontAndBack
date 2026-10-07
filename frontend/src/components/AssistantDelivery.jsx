export default function AssistantDelivery({ message, assistant, onRetrySuccess }) {
  if (!message.delivery_error) return null;
  return <div role="alert" className="mt-2 text-xs text-amber-300"><p>{message.delivery_error}</p><button type="button" className="underline mt-1" disabled={assistant.sending} onClick={async () => { if (await assistant.retry()) onRetrySuccess?.(); }}>Tentar novamente</button></div>;
}

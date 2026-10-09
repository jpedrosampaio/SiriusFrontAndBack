// Decimal strings are formatted without binary floating-point money arithmetic.
export function formatBRL(value) {
  if (value === null || value === undefined) return 'Não informado';
  const match = /^(-?)(\d+)(?:\.(\d{1,2}))?$/.exec(String(value));
  if (!match) return 'Valor indisponível';
  return `${match[1]}R$ ${match[2].replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${(match[3] || '').padEnd(2, '0')}`;
}

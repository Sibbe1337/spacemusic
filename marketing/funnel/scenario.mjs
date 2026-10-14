export function numberInput(value) {
  if (typeof value === 'string' && !/^(?:\d+\.?\d*|\.\d+)$/.test(value.trim())) return null;
  if (typeof value !== 'number' && typeof value !== 'string') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function scenario(monthly, multiple, share) {
  const values = [monthly, multiple, share].map(numberInput);
  if (values.some(value => value === null)) return null;
  const [net, assumed, percent] = values;
  if (net < 0 || assumed <= 0 || percent < 0 || percent > 100) return null;
  const annual = net * 12;
  const total = annual * assumed * (percent / 100);
  return Number.isFinite(total) && Number.isFinite(annual) ? { annual, total } : null;
}

export function netFromReceipts(receipts, payouts, costs) {
  const values = [receipts, payouts, costs].map(numberInput);
  if (values.some(value => value === null)) return null;
  const [gross, royalty, operating] = values;
  if (gross < 0 || royalty < 0 || operating < 0 || royalty + operating > 100) return null;
  const net = gross * (1 - (royalty + operating) / 100);
  return Number.isFinite(net) ? net : null;
}

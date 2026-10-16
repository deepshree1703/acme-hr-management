/** Format a salary using the currency's standard fraction digits. */
export function formatSalary(amount, currency) {
  try {
    // JPY has no minor unit, so its Intl currency default has no decimal places.
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })} ${currency}`;
  }
}

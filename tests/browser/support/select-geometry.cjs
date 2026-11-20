const assert = require('node:assert/strict');

async function assertSelectGeometry(select, context) {
  const spacing = await select.evaluate(control => {
    const wrapper = control.parentElement;
    const icon = wrapper.querySelector(':scope > .lixity-icon');
    if (control.type !== 'select-one' || !wrapper.classList.contains('ctl-select') || !icon) return null;
    const field = control.getBoundingClientRect();
    const arrow = icon.getBoundingClientRect();
    const style = getComputedStyle(control);
    const rtl = style.direction === 'rtl';
    const labelInset = parseFloat(style.paddingInlineStart);
    const labelEnd = parseFloat(style.paddingInlineEnd);
    const arrowInset = rtl ? arrow.left - field.left : field.right - arrow.right;
    const arrowSpan = rtl ? arrow.right - field.left : field.right - arrow.left;
    return {
      clipped: control.scrollWidth > control.clientWidth || field.left < -1 || field.right > innerWidth + 1,
      textSpace: field.width - labelInset - labelEnd,
      insetDifference: labelInset - arrowInset,
      arrowGap: labelEnd - arrowSpan,
      centerOffset: (field.top + field.bottom - arrow.top - arrow.bottom) / 2,
      decorative: icon.getAttribute('aria-hidden') === 'true' && getComputedStyle(icon).pointerEvents === 'none',
    };
  });
  assert(spacing, `${context} uses the shared native select`);
  assert(!spacing.clipped && spacing.textSpace > 0, `${context} fits without text or viewport overflow`);
  assert(Math.abs(spacing.insetDifference) < 1, `${context} has aligned logical insets`);
  assert(spacing.arrowGap > 1, `${context} leaves a gap between text and its arrow`);
  assert(Math.abs(spacing.centerOffset) < 1 && spacing.decorative, `${context} has a centered decorative arrow`);
}

module.exports = {assertSelectGeometry};

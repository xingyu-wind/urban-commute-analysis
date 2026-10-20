import { writeFileSync } from 'node:fs'
import path from 'node:path'

export const responsiveWidths = [320, 375, 390, 768, 1024, 1440]

export async function measureLayout(page, root = 'body') {
  return page.evaluate(selector => {
    const scope = document.querySelector(selector)
    const box = element => {
      const rect = element.getBoundingClientRect()
      return { left: rect.left, right: rect.right, width: rect.width, height: rect.height }
    }
    const critical = [...scope.querySelectorAll('input,select,button,h1,h2,h3,[role="alert"],.kpi-card strong,.traffic-filters,.road-filters,.pagination,.panel,.analysis-panel,.data-notice')]
      .filter(element => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden')
    const outside = critical.filter(element => {
      const rect = box(element)
      return rect.left < 0 || rect.right > innerWidth || rect.width <= 0 || rect.height <= 0
    }).map(element => ({ tag: element.tagName, class: element.className, text: element.textContent.slice(0, 100), ...box(element) }))
    const clippedKpis = [...scope.querySelectorAll('.kpi-card strong,.kpi-card p')].filter(element => {
      const range = document.createRange()
      range.selectNodeContents(element)
      const card = element.closest('.kpi-card').getBoundingClientRect()
      return [...range.getClientRects()].some(rect => rect.left < card.left || rect.right > card.right)
    }).map(element => element.textContent)
    const charts = [...scope.querySelectorAll('.traffic-chart')].map(element => ({
      containerWidth: element.clientWidth, containerHeight: element.clientHeight,
      scrollWidth: element.scrollWidth, overflowX: getComputedStyle(element).overflowX,
      rendererWidth: element.firstElementChild?.getBoundingClientRect().width,
      svgWidth: element.querySelector('svg')?.getBoundingClientRect().width,
    }))
    const tables = [...scope.querySelectorAll('.table-scroll')].filter(element => element.getClientRects().length).map(element => {
      const maximum = Math.max(0, element.scrollWidth - element.clientWidth)
      element.scrollLeft = maximum
      const lastColumnReachable = Math.abs(element.scrollLeft - maximum) <= 1
      element.scrollLeft = 0
      return { clientWidth: element.clientWidth, scrollWidth: element.scrollWidth, lastColumnReachable }
    })
    // Inspect enabled and disabled controls: neither may be hidden behind another surface.
    const obstructed = [...scope.querySelectorAll('input,select,button')].filter(element => {
      if (!element.getClientRects().length || getComputedStyle(element).visibility === 'hidden') return false
      element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' })
      const rect = element.getBoundingClientRect()
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2)
      return !hit || (hit !== element && !element.contains(hit))
    }).map(element => ({ tag: element.tagName, label: element.getAttribute('aria-label') || element.textContent }))
    return { viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth, outside, clippedKpis, obstructed, charts, tables }
  }, root)
}

export async function checkResponsiveMatrix(page, expect, output, name, root = 'body') {
  const results = []
  for (const width of responsiveWidths) {
    await page.setViewportSize({ width, height: 900 })
    // The page boundary must hold immediately, even before chart resize delivery.
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await expect.poll(() => page.locator(`${root} .traffic-chart`).evaluateAll(elements => elements.every(element =>
      element.clientWidth > 0 && element.firstElementChild?.getBoundingClientRect().width <= element.clientWidth
        && element.querySelector('svg')?.getBoundingClientRect().width <= element.clientWidth))).toBe(true)
    const measurement = await measureLayout(page, root)
    results.push(measurement)
    writeFileSync(path.join(output, `${name}-layout.json`), JSON.stringify(results, null, 2) + '\n')
    expect(measurement.scrollWidth <= measurement.viewport).toBe(true)
    expect(measurement.outside).toEqual([])
    expect(measurement.clippedKpis).toEqual([])
    expect(measurement.obstructed).toEqual([])
    expect(measurement.tables.every(table => table.lastColumnReachable)).toBe(true)
    expect(measurement.charts.every(chart => chart.containerWidth > 0 && chart.containerHeight > 0)).toBe(true)
    await page.screenshot({ path: path.join(output, `${name}-${width}.png`), fullPage: true })
  }
  return results
}

/** Delay only chart observer delivery to exercise the actual pre-callback resize window.
 * Native ResizeObserver entries and real Java HTTP responses remain in use.
 */
export async function installResizeProbe(context) {
  await context.addInitScript(() => {
    const NativeObserver = window.ResizeObserver
    window.__pendingChartResizes = []
    window.ResizeObserver = class extends NativeObserver {
      constructor(callback) {
        super((entries, observer) => {
          if (window.__deferChartResize) window.__pendingChartResizes.push(() => callback(entries, observer))
          else callback(entries, observer)
        })
      }
    }
  })
}

export async function checkDeferredChartResize(page, expect, output) {
  await page.setViewportSize({ width: 1024, height: 768 })
  await expect.poll(() => page.locator('.traffic-chart').evaluateAll(elements => elements.every(element =>
    element.firstElementChild.clientWidth === element.clientWidth))).toBe(true)
  await page.evaluate(() => { window.__deferChartResize = true })
  try {
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const held = await measureLayout(page)
    expect(held.charts.some(chart => chart.rendererWidth > chart.containerWidth)).toBe(true)
    expect(held.charts.every(chart => chart.overflowX === 'auto')).toBe(true)
    const reachable = await page.locator('.traffic-chart').evaluateAll(elements => elements.every(element => {
      element.scrollLeft = element.scrollWidth
      const reached = element.scrollWidth <= element.clientWidth || element.scrollLeft > 0
      element.scrollLeft = 0
      return reached
    }))
    expect(reachable).toBe(true)
    writeFileSync(path.join(output, 'deferred-chart-resize.json'), JSON.stringify({ held, fullChartReachableByInternalScroll: reachable }, null, 2) + '\n')
  } finally {
    await page.evaluate(() => {
      window.__deferChartResize = false
      window.__pendingChartResizes.splice(0).forEach(callback => callback())
    })
  }
  // Check the real observer completes the resize; containment must not hide a broken lifecycle.
  await expect.poll(() => page.locator('.traffic-chart').evaluateAll(elements => elements.every(element =>
    element.firstElementChild.clientWidth === element.clientWidth && element.scrollWidth === element.clientWidth))).toBe(true)
}

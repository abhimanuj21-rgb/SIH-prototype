import { useEffect, useRef } from 'react'

const INTERACTIVE = [
  'a', 'button', '.btn', 'select', 'label', '[role="button"]',
  '.nav a', '.toggle', '.lp-gov__card', '.lp-check', '.lp-step',
  'input[type="checkbox"]', 'input[type="radio"]',
].join(', ')
const TEXT_FIELD = 'input, textarea, [contenteditable="true"]'
const NATIVE_ZONE = '.leaflet-container'

export default function CustomCursor() {
  const dotRef = useRef(null)
  const ringRef = useRef(null)

  useEffect(() => {
    if (!window.matchMedia('(pointer: fine)').matches) return

    const dot = dotRef.current
    const ring = ringRef.current
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const ease = reduceMotion ? 1 : 0.22

    document.documentElement.classList.add('cc-enabled')

    let x = window.innerWidth / 2
    let y = window.innerHeight / 2
    let ringX = x
    let ringY = y

    const onMove = (e) => {
      x = e.clientX
      y = e.clientY
      dot.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`

      const el = e.target
      const inNative = el.closest?.(NATIVE_ZONE)
      const inText = el.closest?.(TEXT_FIELD)
      const inInteractive = el.closest?.(INTERACTIVE)
      const hidden = !!inNative || !!inText

      dot.classList.toggle('cc-hidden', hidden)
      ring.classList.toggle('cc-hidden', hidden)
      dot.classList.toggle('cc-hover', !!inInteractive && !hidden)
      ring.classList.toggle('cc-hover', !!inInteractive && !hidden)
    }

    let raf = requestAnimationFrame(function tick() {
      ringX += (x - ringX) * ease
      ringY += (y - ringY) * ease
      ring.style.transform = `translate(${ringX}px, ${ringY}px) translate(-50%, -50%)`
      raf = requestAnimationFrame(tick)
    })

    const onLeaveWindow = () => { dot.style.opacity = '0'; ring.style.opacity = '0' }
    const onEnterWindow = () => { dot.style.opacity = ''; ring.style.opacity = '' }

    window.addEventListener('mousemove', onMove)
    document.documentElement.addEventListener('mouseleave', onLeaveWindow)
    document.documentElement.addEventListener('mouseenter', onEnterWindow)

    return () => {
      document.documentElement.classList.remove('cc-enabled')
      window.removeEventListener('mousemove', onMove)
      document.documentElement.removeEventListener('mouseleave', onLeaveWindow)
      document.documentElement.removeEventListener('mouseenter', onEnterWindow)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <>
      <div ref={ringRef} className="cc-ring" aria-hidden="true" />
      <div ref={dotRef} className="cc-dot" aria-hidden="true" />
    </>
  )
}

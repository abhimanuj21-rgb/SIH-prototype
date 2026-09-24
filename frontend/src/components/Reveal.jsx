import useReveal from '../hooks/useReveal.js'
import useTilt from '../hooks/useTilt.js'

export default function Reveal({ as: Tag = 'div', delay = 0, tilt = 0, className = '', style, children, ...rest }) {
  const [revealRef, visible] = useReveal()
  const tiltRef = useTilt(tilt)

  const setRefs = (node) => {
    revealRef.current = node
    tiltRef.current = node
  }

  return (
    <Tag
      ref={tilt ? setRefs : revealRef}
      className={`reveal${visible ? ' in' : ''}${className ? ' ' + className : ''}`}
      style={{ transitionDelay: visible ? `${delay}ms` : '0ms', ...style }}
      {...rest}
    >
      {children}
    </Tag>
  )
}

import { Rnd } from 'react-rnd'
import useStore from '../../../../../store/useStore'

const MpFloating = ({ children }: any) => {
  const swX = useStore((state) => state.spotify.swX)
  const setSwX = useStore((state) => state.setSwX)
  const swY = useStore((state) => state.spotify.swY)
  const setSwY = useStore((state) => state.setSwY)

  return (
    <Rnd
      size={{ width: 960, height: 'auto' }}
      position={{ x: swX, y: swY }}
      onDragStop={(e, d) => {
        setSwX(d.x)
        setSwY(d.y)
      }}
      onResizeStop={(_e, _direction, ref, _delta, position) => {
        setSwX(position.x)
        setSwY(position.y)
      }}
      style={{ zIndex: 10 }}
    >
      {children}
    </Rnd>
  )
}

export default MpFloating

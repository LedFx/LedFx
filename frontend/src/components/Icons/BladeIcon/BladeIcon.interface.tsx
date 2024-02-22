export interface BladeIconProps {
  /**
   * flag indicator
   */
  colorIndicator?: boolean
  /**
   * Icon is rendered in SceneList
   */
  scene?: boolean
  /**
   * Icon is rendered in SceneList
   */
  card?: boolean
  /**
   * Icon is rendered in Intro
   */
  intro?: boolean
  /**
   * examples: `wled`, `Light`, `mdi:led-strip`
   */
  name?: string
  /**
   * JSX className
   */
  className?: string
  /**
   * JSX style
   */
  style?: Record<string, unknown>
}

export const BladeIconDefaultProps = {
  colorIndicator: false,
  name: 'MusicNote',
  className: '',
  style: {},
  scene: false,
  card: false
}

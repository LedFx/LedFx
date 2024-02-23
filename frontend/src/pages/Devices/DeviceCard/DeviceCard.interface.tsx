export interface DeviceCardProps {
  /**
   * The Name of the device
   */
  deviceName?: string
  /**
   * IconName. Refer to `Icon`
   */
  iconName?: string
  /**
   * Name of the current Effect
   */
  effectName: string | undefined
  /**
   * Flag if Effect is set
   */
  isEffectSet?: boolean
  /**
   * Is device online
   */
  online?: boolean
  /**
   * Play/Pause
   */
  isPlaying?: boolean
  /**
   * Is streaming from other sources
   */
  isStreaming?: boolean
  /**
   * Do not send to leds
   */
  previewOnly?: boolean
  /**
   * TransitionTime of the Device
   */
  transitionTime?: number
  /**
   * DeviceId if its a device, else undefined if its a virtual
   */
  isDevice?: string | undefined
  /**
   * Graphs active?
   */
  graphsActive?: boolean
  /**
   * Do not send to leds
   */
  graphsMulti?: boolean
  /**
   * Show Matrix
   */
  showMatrix?: boolean
  /**
   * Colorize?
   */
  colorIndicator?: boolean
  /**
   * VirtualId
   */
  virtId?: string
  /**
   * Index
   */
  index?: number
  /**
   * Handle Function
   */
  handleDeleteDevice?: any
  /**
   * Handle Function
   */
  handleEditVirtual?: any
  /**
   * Handle Function
   */
  handleEditDevice?: any
  /**
   * Handle Function
   */
  handleClearEffect?: any
  /**
   * Handle Function
   */
  handlePlayPause?: any
  /**
   * Handle Function
   */
  activateDevice?: any
  /**
   * Handle Function
   */
  linkTo?: any
  /**
   * onClick Link
   */
  additionalStyle?: any
  /**
   * JSX styles
   */
}
export const DeviceCardDefaults: DeviceCardProps = {
  deviceName: 'My Wled',
  online: true,
  effectName: undefined,
  virtId: 'yz-quad',
  index: 1,
  handleDeleteDevice: () => console.log('DELETING DEVICE'), // eslint-disable-line no-console
  handleEditVirtual: () => console.log('EDITING VIRTUAL'), // eslint-disable-line no-console
  handleEditDevice: () => console.log('EDITING DEVICE'), // eslint-disable-line no-console
  handleClearEffect: () => console.log('CLEARING EFFECT'), // eslint-disable-line no-console
  handlePlayPause: () => console.log('PLAY/PAUSE'), // eslint-disable-line no-console
  linkTo: '/',
  additionalStyle: {},
  iconName: 'wled',
  colorIndicator: true,
  isPlaying: true,
  isStreaming: false,
  previewOnly: true,
  isEffectSet: true,
  transitionTime: 5,
  isDevice: 'yz-quad',
  graphsActive: true,
  showMatrix: false
}

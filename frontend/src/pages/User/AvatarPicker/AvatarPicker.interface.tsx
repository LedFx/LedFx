import { Edit, GitHub } from '@mui/icons-material'

const IStorage = ['localStorage', 'indexedDb', 'cloud', 'custom'] as const
export const storageOptions = [
  'localStorage',
  'indexedDb',
  'cloud',
  'custom'
] as typeof IStorage
export interface AvatarPickerProps {
  /**
   * Where to store the avatar
   */
  storage?: (typeof IStorage)[number]
  /**
   * Custom storage setter (if provided, localStorage and indexedDb are ignored)
   */
  setAvatar?: ((_dataUri: string) => void) | null
  /**
   * Custom storage getter (if provided, localStorage and indexedDb are ignored)
   */
  avatar?: string
  /**
   * Custom storage key (for localStorage or indexedDb). Defaults to 'avatar'
   */
  storageKey?: string
  /**
   * Icon to show when no avatar is set
   */
  defaultIcon?: any
  /**
   * Hover-Icon to show when avatar is set
   */
  editIcon?: any
  /**
   * Size of the avatar
   */
  size?: number
  /**
   * Initial zoom level
   * */
  initialZoom?: number
  /**
   * Minimum zoom level
   */
  minZoom?: number
  /**
   * Maximum zoom level
   */
  maxZoom?: number
  /**
   * Zoom step
   */
  stepZoom?: number
  /**
   * Minimum rotation
   */
  minRotation?: number
  /**
   * Maximum rotation
   */
  maxRotation?: number
  /**
   * Rotation step
   */
  stepRotation?: number
  /**
   * Props to pass to the Avatar component
   */
  props?: any
}

export const AvatarPickerDefaults: AvatarPickerProps = {
  size: 150,
  defaultIcon: <GitHub sx={{ fontSize: 'min(25vw, 25vh, 150px)' }} />,
  editIcon: (
    <Edit
      sx={{
        position: 'absolute',
        bottom: 0,
        right: 0,
        left: 0,
        top: 0,
        width: '100%',
        height: '100%',
        padding: '3rem',
        opacity: 0,
        borderRadius: '50%',
        background: '#0009',
        '&:hover': { opacity: 1 }
      }}
    />
  ),
  avatar: undefined,
  initialZoom: 1,
  minZoom: 0.01,
  maxZoom: 3,
  stepZoom: 0.01,
  minRotation: 0,
  maxRotation: 360,
  stepRotation: 0.01,
  setAvatar: null,
  storage: 'indexedDb',
  storageKey: 'avatar',
  props: {}
}

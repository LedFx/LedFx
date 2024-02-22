import { SettingsRow } from './SettingsComponents'
import useStore from '../../store/useStore'

const IntegrationsSection = () => {
  const setFeatures = useStore((state) => state.setFeatures)
  const features = useStore((state) => state.features)

  return (
    <SettingsRow
      title="Spotify Pro"
      checked={features.spotifypro}
      onChange={() => setFeatures('spotifypro', !features.spotifypro)}
    />
  )
}

export default IntegrationsSection

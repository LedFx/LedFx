import useStore from '../../store/useStore'
import { SettingsRow } from './SettingsComponents'

const AlphaFeatures = () => {
  const setFeatures = useStore((state) => state.setFeatures)
  const showFeatures = useStore((state) => state.showFeatures)
  const features = useStore((state) => state.features)

  return (
    <>
      <SettingsRow
        title="LedFx Cloud"
        checked={features.cloud}
        onChange={() => setFeatures('cloud', !features.cloud)}
      />
      <SettingsRow
        title="WebAudio"
        checked={features.webaudio}
        onChange={() => setFeatures('webaudio', !features.webaudio)}
      />
      <SettingsRow
        title="Matrix 2D"
        checked={features.matrix}
        onChange={() => setFeatures('matrix', !features.matrix)}
      />
      {features.integrations && (
        <>
          <SettingsRow
            title="MQTT"
            checked={features.mqtt}
            onChange={() => setFeatures('mqtt', !features.mqtt)}
          />
          <SettingsRow
            title="MQTT HA"
            checked={features.mqtt_hass}
            onChange={() => setFeatures('mqtt_hass', !features.mqtt_hass)}
          />
        </>
      )}
      {showFeatures.wled && (
        <SettingsRow
          title="WLED Integration"
          checked={features.wled}
          onChange={() => setFeatures('wled', !features.wled)}
        />
      )}
    </>
  )
}

export default AlphaFeatures

import { SettingsRow } from './SettingsComponents'
import useStore from '../../store/useStore'

const ScenesSection = () => {
  const setFeatures = useStore((state) => state.setFeatures)
  const features = useStore((state) => state.features)
  const infoAlerts = useStore((state) => state.ui.infoAlerts)
  const setInfoAlerts = useStore((state) => state.ui.setInfoAlerts)

  return (
    <>
      <SettingsRow
        title="Show Infobox on Scenes page"
        checked={infoAlerts.scenes}
        onChange={() => setInfoAlerts('scenes', !infoAlerts.scenes)}
        direct
      />
      <SettingsRow
        title="SceneTables (Recent+Most)"
        checked={features.scenetables}
        onChange={() => setFeatures('scenetables', !features.scenetables)}
      />
      <SettingsRow
        title="SceneChips (Filter Tags)"
        checked={features.scenechips}
        onChange={() => setFeatures('scenechips', !features.scenechips)}
      />
      <SettingsRow
        title="Scene external call"
        checked={features.sceneexternal}
        onChange={() => setFeatures('sceneexternal', !features.sceneexternal)}
      />
      <SettingsRow
        title="Assign MIDI & Activate Scene"
        checked={features.scenemidi}
        onChange={() => setFeatures('scenemidi', !features.scenemidi)}
      />
    </>
  )
}

export default ScenesSection

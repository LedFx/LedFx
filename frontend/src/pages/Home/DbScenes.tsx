import { useTheme, Stack } from '@mui/material'
import BladeFrame from '../../components/SchemaForm/components/BladeFrame'
import ScenesMostUsed from '../Scenes/ScenesMostUsed'
import useStore from '../../store/useStore'

const DbScenes = () => {
  const theme = useTheme()
  const scenes = useStore((state) => state.scenes)
  const captivateScene = useStore((state) => state.captivateScene)
  const activateScene = useStore((state) => state.activateScene)

  const handleActivateScene = (e: string) => {
    activateScene(e)
    if (scenes[e]?.scene_puturl && scenes[e]?.scene_payload)
      captivateScene(scenes[e]?.scene_puturl, scenes[e]?.scene_payload)
  }
  return (
    <BladeFrame
      labelStyle={{
        background: theme.palette.background.default,
        color: theme.palette.primary.main
      }}
      style={{
        borderColor: theme.palette.primary.main,
        padding: 20,
        minWidth: 280
      }}
      title="Most used Scenes"
    >
      <Stack width="100%">
        <ScenesMostUsed
          db
          scenes={scenes}
          activateScene={handleActivateScene}
        />
      </Stack>
    </BladeFrame>
  )
}

export default DbScenes

import { useEffect } from 'react'

import {
  Card,
  CardActionArea,
  CardActions,
  Typography,
  Grid,
  Chip,
  useTheme,
  Alert,
  Collapse
} from '@mui/material'
import useStore from '../../store/useStore'
import NoYet from '../../components/NoYet'
// import ScenesTable from './ScenesTable';
import ScenesRecent from './ScenesRecent'
import ScenesMostUsed from './ScenesMostUsed'
import ScenesPlaylist from './ScenesPlaylist'
import ScenesMenu from './ScenesMenu'
import useStyles from './Scenes.styles'
import SceneImage from './ScenesImage'

const Scenes = () => {
  const classes = useStyles()
  const theme = useTheme()
  const getScenes = useStore((state) => state.getScenes)
  const scenes = useStore((state) => state.scenes)
  const features = useStore((state) => state.features)
  const activateScene = useStore((state) => state.activateScene)
  const infoAlerts = useStore((state) => state.ui.infoAlerts)
  const setInfoAlerts = useStore((state) => state.ui.setInfoAlerts)
  const sceneActiveTags = useStore((state) => state.ui.sceneActiveTags)

  const toggletSceneActiveTag = useStore(
    (state) => state.ui.toggletSceneActiveTag
  )
  const captivateScene = useStore((state) => state.captivateScene)

  const handleActivateScene = (e: string) => {
    activateScene(e)
    if (scenes[e]?.scene_puturl && scenes[e]?.scene_payload)
      captivateScene(scenes[e]?.scene_puturl, scenes[e]?.scene_payload)
  }

  useEffect(() => {
    getScenes()
  }, [getScenes])

  const sceneFilter = (sc: string) =>
    scenes[sc].scene_tags
      ?.split(',')
      .some((sce: string) => sceneActiveTags.includes(sce))

  return (
    <>
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          flexDirection: 'column'
        }}
      >
        <Collapse in={infoAlerts.scenes}>
          <Alert
            sx={{ mb: 2 }}
            severity="info"
            onClose={() => {
              setInfoAlerts('scenes', false)
            }}
          >
            Head over to Devices-Page and adjust all effects for all devices.
            <br />
            You can then save everything as a scene by using the{' '}
            <strong>+</strong> button
          </Alert>
        </Collapse>
        {scenes && Object.keys(scenes).length && features.scenetables ? (
          <Grid
            container
            spacing={[0, 0, 2, 2, 2]}
            justifyContent="center"
            m={['0 auto', '0 auto', '0.5rem', '0.5rem', '0.5rem']}
            sx={{ maxWidth: '100%' }}
          >
            <Grid
              item
              mt={['0.5rem', '0.5rem', 0, 0, 0]}
              mb={['5rem', '5rem', 0, 0, 0]}
              p="8px !important"
              width={450}
            >
              <ScenesRecent
                scenes={scenes}
                activateScene={handleActivateScene}
                title="Recent Scenes"
              />
            </Grid>
            <Grid
              item
              mt={['0.5rem', '0.5rem', 0, 0, 0]}
              mb={['5rem', '5rem', 0, 0, 0]}
              p="8px !important"
              width={450}
            >
              <ScenesMostUsed
                scenes={scenes}
                activateScene={handleActivateScene}
                title="Most Used Scenes"
              />
            </Grid>
            <Grid
              item
              mt={['0.5rem', '0.5rem', 0, 0, 0]}
              mb={['5rem', '5rem', 0, 0, 0]}
              p="8px !important"
              width={450}
            >
              <ScenesPlaylist
                scenes={scenes}
                activateScene={handleActivateScene}
                title="Playlist"
              />
            </Grid>
          </Grid>
        ) : null}
        {scenes && Object.keys(scenes).length && features.scenechips ? (
          <div>
            {Object.keys(scenes)
              .flatMap((s) =>
                !!scenes[s].scene_tags && scenes[s].scene_tags !== ''
                  ? scenes[s].scene_tags.split(',')
                  : null
              )
              .filter((n: string) => !!n && n.trim())
              .filter((v, i, a) => a.indexOf(v) === i && v)
              .map((t: string) => {
                return (
                  <Chip
                    variant={
                      sceneActiveTags.includes(t) ? 'filled' : 'outlined'
                    }
                    sx={{
                      ml: 1,
                      mt: 1,
                      mr: 1,
                      cursor: sceneActiveTags.includes(t)
                        ? 'zoom-out'
                        : 'zoom-in'
                    }}
                    key={t}
                    label={t}
                    onClick={() => toggletSceneActiveTag(t)}
                  />
                )
              })}
          </div>
        ) : null}
      </div>
      <Grid
        container
        spacing={[0, 0, 2, 2, 2]}
        justifyContent="center"
        m={['0 auto', '0 auto', '0.5rem', '0.5rem', '0.5rem']}
        sx={{ maxWidth: '100%' }}
      >
        {scenes && Object.keys(scenes).length ? (
          (sceneActiveTags.length
            ? Object.keys(scenes).filter(sceneFilter)
            : Object.keys(scenes)
          ).map((s, i) => {
            return (
              <Grid
                item
                key={i}
                mt={['0.5rem', '0.5rem', 0, 0, 0]}
                p="8px !important"
              >
                <Card
                  className={classes.root}
                  sx={{
                    border: '1px solid',
                    borderColor: theme.palette.divider
                  }}
                >
                  <CardActionArea
                    style={{ background: theme.palette.background.default }}
                    onClick={() => handleActivateScene(s)}
                  >
                    <SceneImage
                      iconName={scenes[s].scene_image || 'Wallpaper'}
                    />
                    <div style={{ position: 'absolute', top: 0, right: 0 }}>
                      {scenes[s].scene_tags?.split(',').map(
                        (t: string) =>
                          t.length > 0 &&
                          features.scenechips && (
                            <Chip
                              variant="filled"
                              label={t}
                              key={t}
                              sx={{
                                cursor: 'pointer',
                                backgroundColor: theme.palette.background.paper,
                                border: '1px solid',
                                borderColor: theme.palette.text.disabled
                              }}
                            />
                          )
                      )}
                    </div>
                  </CardActionArea>
                  <CardActions
                    style={{
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      width: '100%'
                    }}
                  >
                    <Typography
                      className={classes.sceneTitle}
                      variant="h5"
                      component="h2"
                    >
                      {scenes[s].name || s}
                    </Typography>
                    {!(
                      window.localStorage.getItem('guestmode') === 'activated'
                    ) && <ScenesMenu sceneId={s} />}
                  </CardActions>
                </Card>
              </Grid>
            )
          })
        ) : (
          <NoYet type="Scene" />
        )}
      </Grid>
      {/* {scenes && Object.keys(scenes).length && <ScenesTable scenes={scenes} />} */}
    </>
  )
}

export default Scenes

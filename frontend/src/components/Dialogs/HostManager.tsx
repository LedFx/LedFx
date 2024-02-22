/* eslint-disable prettier/prettier */
import { useState, useEffect } from 'react';
import {
  Button,
  TextField,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Typography,
  // Switch,
  Divider,
  Box,
  useTheme,
  Card,
  CardActionArea,
  CardActions,
  Stack,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
} from '@mui/material';
import { Add, CalendarViewDay, Delete, FormatListBulleted, PlayArrow } from '@mui/icons-material';
import isElectron from 'is-electron';
import useStore from '../../store/useStore';
import Instances from './Instances';
import SceneImage from '../../pages/Scenes/ScenesImage';
import useStyles from '../../pages/Scenes/Scenes.styles'

export default function HostManager() {
  const theme = useTheme()
  const classes = useStyles()
  const [instanceVariant] = useState<'buttons' | 'line'>('line');
  const [commonScenes, setCommonScenes] = useState<Record<string, any>>({});
  const dialogOpen = useStore((state) => state.hostManager || false);
  const edit = useStore((state) => state.dialogs.nohost?.edit || false);
  const setDialogOpen = useStore((state) => state.setHostManager);
  const setDisconnected = useStore((state) => state.setDisconnected);
  const coreParams = useStore((state) => state.coreParams);
  const coreStatus = useStore((state) => state.coreStatus);
  const setHost = useStore((state) => state.setHost);
  const storedURL = window.localStorage.getItem('ledfx-host');
  const storedURLs = JSON.parse(
    window.localStorage.getItem('ledfx-hosts') ||
      JSON.stringify(['http://localhost:8888'])
  );
  const [hosts, setHosts] = useState(['http://localhost:8888']);
  const [hostvalue, setHostvalue] = useState('http://localhost:8888');

  const handleClose = () => {
    setDialogOpen(false);
  };

  const handleSave = (ho:string, connect?:boolean) => {
    if (connect) setHost(ho);
    if (!hosts.some((h) => h === ho)) {
      window.localStorage.setItem(
        'ledfx-hosts',
        JSON.stringify([...hosts, ho])
      );
      setHosts([...hosts, ho]);
    } else {
      window.localStorage.setItem('ledfx-hosts', JSON.stringify([...hosts]));
      setHosts([...hosts]);
    }
    setDisconnected(false);
    window.location.reload();
  };

  const handleDelete = (e: any, title: string) => {
    e.stopPropagation();
    window.localStorage.setItem(
      'ledfx-hosts',
      JSON.stringify(hosts.filter((h) => h !== title))
    );
    setHosts(hosts.filter((h) => h !== title));
  };


  useEffect(() => {
    if (storedURL) setHostvalue(storedURL);
    if (storedURLs) setHosts(storedURLs);
  }, [storedURL, setHosts]);

  useEffect(() => {
    if (!storedURL) {
      setHost(
        isElectron()
          ? 'http://localhost:8888'
          : window.location.href.split('/#')[0].replace(/\/+$/, '')
      );
      window.localStorage.setItem(
        'ledfx-host',
        isElectron()
          ? 'http://localhost:8888'
          : window.location.href.split('/#')[0].replace(/\/+$/, '')
      );
      // eslint-disable-next-line no-self-assign
      window.location.href = window.location.href;
    }
  }, []);
  const runningCores = Object.keys(coreStatus).filter((h)=>coreStatus[h] === 'running').map((h)=>parseInt(coreParams[h][1], 10) || 8888)


  useEffect(() => {
    async function getCommonScenes(rcores: number[]) {
      try {
        // Fetch all scenes from each core
        const allScenes = await Promise.all(
          rcores.map(async (h:number) => {
            const res = await fetch(`http://localhost:${h}/api/scenes`);
            const json = await res.json();
            return json.scenes;
          })
        );

        // Get the keys of the scenes from each core
        const sceneKeys = allScenes.map((scenes) => Object.keys(scenes));

        // Find the common keys
        const commonKeys = sceneKeys.reduce((a, b) => a.filter(c => b.includes(c) && c !== 'blade-scene'));
        // Prepare an empty object for the final scenes
        const finalScenes: Record<string, any> = {};

        // Iterate over the common keys
        commonKeys.forEach((key) => {
          // Iterate over each scene from all cores
          allScenes.forEach((scenes) => {
            // If the scene is not in finalScenes, add it
            if (!finalScenes[key]) {
              finalScenes[key] = {
                name: scenes[key]?.name,
                scene_image: scenes[key]?.scene_image
              };
            }
            // If the current scene's image is not "Wallpaper", update it in finalScenes
            else if (scenes[key]?.scene_image !== 'Wallpaper') {
              finalScenes[key] = {
                name: scenes[key]?.name,
                scene_image: scenes[key]?.scene_image
              };
            }
          });
        });

        return finalScenes;
      } catch (_e) {
        // console.log(_e);
        return {};
      }
    }

    getCommonScenes(runningCores).then((res)=>setCommonScenes(res));



  }, [coreStatus, coreParams]);
  // console.log(commonScenes)
  const activateCommon = async (scene: string) => {
    try {
      await Promise.all(
        runningCores.map(async (h:number) => {
          const res = await fetch(`http://localhost:${h}/api/scenes`, {method: 'PUT', body: JSON.stringify({
            id: scene,
            action: 'activate_in',
            ms: 0
          })});
          const json = await res.json();
          return json.scenes;
        })
      );
    }
    catch (_e) {
      // console.log(_e);
    }
  }

  const [alignment, setAlignment] = useState('cards');

  const handleChange = (
    event: React.MouseEvent<HTMLElement>,
    newAlignment: string,
  ) => {
    setAlignment(newAlignment);
  };

  return (
    <div key="nohost-dialog">
      <Dialog
        open={dialogOpen}
        onClose={handleClose}
        aria-labelledby="form-dialog-title"
      >
        <DialogTitle id="form-dialog-title">
          LedFx HostManager <span style={{ background: theme.palette.success.dark, padding: '0 1rem', borderRadius: 3, marginLeft: 8 }}>beta</span>
        </DialogTitle>
        <DialogContent>
          {!edit && (
            <DialogContentText>
              You can change the host if you want:
            </DialogContentText>
          )}
          <div style={{ display: 'flex', marginTop: '0.5rem' }}>
            <TextField label="IP:Port" variant="outlined" value={hostvalue} onKeyDown={(e) => e.key === 'Enter' && setHosts([...hosts,hostvalue])} onChange={(e) => setHostvalue(e.target.value)} />
            <Button aria-label="add" onClick={() => setHosts([...hosts,hostvalue])}>
              <Add />
            </Button>
          </div>
          <Typography variant='caption'> Known Hosts</Typography>
          <div>
            {hosts.map(h=><div key={h}>
              <div style={{ display: 'flex' }}>
                <Button size="medium" sx={{ textTransform: 'none' }} fullWidth aria-label="connect" onClick={() => {
                  setHostvalue(h)
                  handleSave(h)
                }}>
                  {h}
                </Button>
                <Button aria-label="delete" onClick={(e) => h && handleDelete(e, h)}>
                  <Delete />
                </Button>
              </div>
            </div>)}
          </div>
          {isElectron() && window.process?.argv.indexOf('integratedCore') !== -1 && (<div style={{ marginTop: '1rem'}}>
            <div style={{ marginBottom: '1rem'}}>

              <Typography variant='caption' sx={{ marginBottom: '1rem' }}>Core Instances</Typography>
              <Divider sx={{ marginBottom: '1rem' }} />
            </div>
            {instanceVariant === 'line' && <><Box display="flex">
              <Box sx={{width: '60px', margin: '0 1rem'}}>Port</Box>
              <Box sx={{width: '90px', marginRight: '0.5rem'}}>Status</Box>
              <Box sx={{width: '90px', marginRight: '0.5rem'}}>Instance</Box>
              {/* <Box sx={{width: '110px', marginRight: '0.5rem'}}>Config</Box> */}
              <Box sx={{flexGrow: 1, marginRight: '0.5rem', textAlign: 'left', paddingLeft: '0.5rem'}}>Actions</Box>
            </Box>
            <Divider sx={{ marginBottom: '1rem' }} />
            <Divider/>
            </>}

            {Object.keys(coreParams).map((h, i)=><Instances handleDeleteHost={handleDelete}  handleSave={handleSave} instances={Object.keys(coreParams).map((ho)=>parseInt(coreParams[ho][1], 10) || 8888)} variant={instanceVariant} i={i} instance={h} port={coreParams[h].length > 0 ? coreParams[h][1] : '8888'} key={coreParams[h].length > 0 ? coreParams[h][1] : '8888'} />)}
            <Instances handleSave={handleSave} handleDeleteHost={handleDelete} instances={Object.keys(coreParams).map((ho)=>parseInt(coreParams[ho][1], 10) || 8888)}variant={instanceVariant} instance={false} i={Object.keys(coreParams).length + 1} port={`${parseInt(coreParams[`instance${  Object.keys(coreParams).length }`]?.[1] || '8888', 10) + 1}`} />
          </div>)}

          <div style={{ marginTop: '1rem'}}>
            <div style={{ marginBottom: '1rem'}}>
              <Stack direction="row" spacing={2} justifyContent="space-between" alignItems="center">
                <Tooltip title="Same scene id with different scene config across all running cors. ATTENTION: You have to make sure yourself, they are not colliding!">
                  <Typography variant='caption' sx={{ marginBottom: '1rem' }}>Common Scenes <span style={{ background: theme.palette.success.dark, padding: '0 1rem', borderRadius: 3, marginLeft: 8 }}>alpha</span></Typography>
                </Tooltip>
                {Object.keys(commonScenes).length > 0 && (
                  <ToggleButtonGroup
                    size="small"
                    value={alignment}
                    exclusive
                    onChange={handleChange}
                    aria-label="text alignment"
                  >
                    <ToggleButton value="list" aria-label="left aligned">
                      <FormatListBulleted />
                    </ToggleButton>
                    <ToggleButton value="cards" aria-label="centered">
                      <CalendarViewDay />
                    </ToggleButton>
                  </ToggleButtonGroup>
                )}
              </Stack>
              <Divider sx={{ marginBottom: '1rem' }} />
            </div>
            {Object.keys(commonScenes).length > 0 && (
              <>
                {alignment === 'list' && <><Box display="flex">
                  <Box sx={{width: '240px', margin: '0 2rem 0 1rem'}}>Scene</Box>
                  <Box sx={{flexGrow: 1, marginRight: '0.5rem', textAlign: 'left', paddingLeft: '0.5rem'}}>Actions</Box>
                </Box>
                <Divider sx={{ marginBottom: '1rem' }} />
                <Divider/></>}
                {Object.keys(commonScenes).map((sc: string) => alignment === 'cards' ? (
                  <Card key={sc}
                    className={classes.root}
                    sx={{
                      border: '1px solid',
                      borderColor: theme.palette.divider,
                      margin: '0.5rem'
                    }}>
                    <CardActionArea
                      style={{ background: theme.palette.background.default }}
                      onClick={() => activateCommon(sc)}>
                      <SceneImage
                        iconName={commonScenes[sc].scene_image || 'Wallpaper'}
                      />
                    </CardActionArea>
                    <CardActions>
                      <Typography key={sc}
                        className={classes.sceneTitle}
                        variant="h5"
                        component="h2"
                      >
                        {commonScenes[sc].name}
                      </Typography>
                    </CardActions>
                  </Card>
                ) : (
                  <>
                    <Stack direction="row" spacing={2} alignItems="center" height="calc(32px + 0.5rem)" >
                      <Box width={90} height={32} marginTop="0.25rem" marginBottom="0.25rem" marginRight="2rem" overflow="hidden">
                        <SceneImage key={sc} iconName={commonScenes[sc].scene_image || 'Wallpaper'} />
                      </Box>
                      <Typography key={sc}
                        className={classes.sceneTitle}
                        variant="h5"
                        component="h2"
                        width={165}
                      >
                        {commonScenes[sc].name}
                      </Typography>

                      <Button
                        variant="text"
                        sx={{ minWidth: '32px', width: '32px' }}
                        aria-label="connect"
                        onClick={() => {
                          activateCommon(sc)
                        }}
                      >
                        <PlayArrow />
                      </Button>
                    </Stack>
                    <Divider />
                  </>
                )
                )}
              </>
            )}
          </div>

        </DialogContent>
        <DialogActions>
          {/* <DialogActions sx={{ justifyContent: 'space-between'}}>
          <div>
            <Switch sx={{ml: 1}} checked={instanceVariant === 'line'} onChange={() => setInstanceVariant(instanceVariant === 'line' ? 'buttons' : 'line')} />
            <Typography variant='caption' sx={{ marginTop: '1rem' }}>Show as list</Typography>
          </div> */}
          <Button onClick={handleClose} color="primary">
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
}

/* eslint-disable @typescript-eslint/indent */
/* eslint-disable no-self-assign */
/* eslint-disable no-alert */
import {
  Badge,
  Box,
  Divider,
  Select,
  Stack,
  Step,
  StepButton,
  Stepper,
  TextField,
  Tooltip,
  useTheme,
  MenuItem,
  Collapse,
  Alert
} from '@mui/material'
import {
  AccessTime,
  CloudDownload,
  CloudUpload,
  EmojiEventsOutlined,
  GitHub,
  Star,
  StarOutline,
  Tune
} from '@mui/icons-material'
import axios from 'axios'
import { useEffect, useState } from 'react'
import Accordion from '@mui/material/Accordion'
import AccordionDetails from '@mui/material/AccordionDetails'
import AccordionSummary from '@mui/material/AccordionSummary'
import Typography from '@mui/material/Typography'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import useStore from '../../store/useStore'
import Popover from '../../components/Popover/Popover'
import AvatarPicker from './AvatarPicker/AvatarPicker'

const User = () => {
  const theme = useTheme()
  const [expanded, setExpanded] = useState<string | false>(false)
  const [subExpanded, setSubExpanded] = useState<string | false>(false)
  const [cloudEffects, setCloudEffects] = useState<any>([])
  const [cloudConfigs, setCloudConfigs] = useState<any>([])
  const [configName, setConfigName] = useState('')
  const [cloudPlaylists, setCloudPlaylists] = useState<any>([])
  const [playlistName, setPlaylistName] = useState('')
  const [availableThemes, setAvailableThemes] = useState(0)

  const [starred, setStarred] = useState({
    core: false,
    client: false,
    build: false,
    hass: false,
    wledman: false,
    audiopipes: false,
    io: false
  })
  const [trophies, setTrophies] = useState({
    fan: 0,
    enthusiast: 0,
    contributor: 0
  })
  // const trophies = useStore((state) => state.user.trophies)
  // const setTrophies = useStore((state) => state.user.setTrophies)
  // const starred = useStore((state) => state.user.starred)
  // const setStarred = useStore((state) => state.user.setStarred)

  const infoAlerts = useStore((state) => state.ui.infoAlerts)
  const setInfoAlerts = useStore((state) => state.ui.setInfoAlerts)
  const getFullConfig = useStore((state) => state.getFullConfig)
  const isLogged = useStore((state) => state.isLogged)
  const importSystemConfig = useStore((state) => state.importSystemConfig)
  const setSystemConfig = useStore((state) => state.setSystemConfig)
  const scenePL = useStore((state) => state.scenePL)
  const setScenePL = useStore((state) => state.setScenePL)
  // const [avatar, setAvatar] = useState<undefined | string>(undefined)

  const userName = localStorage.getItem('username')

  const cloud = axios.create({
    baseURL: 'https://strapi.yeonv.com'
  })

  const filteredCloudEffects = {} as any
  Object.keys(cloudEffects).forEach((effectGroup) => {
    const filteredEffects = cloudEffects[effectGroup].filter((effect: any) => {
      return effect.user && effect.user.username === userName
    })

    if (filteredEffects.length > 0) {
      filteredCloudEffects[effectGroup] = filteredEffects
    }
  })

  const handleChange =
    (panel: string) => (event: React.SyntheticEvent, isExpanded: boolean) => {
      setExpanded(isExpanded ? panel : false)
    }
  const handleChangeSub =
    (panel: string) => (event: React.SyntheticEvent, isExpanded: boolean) => {
      setSubExpanded(isExpanded ? panel : false)
    }
  const getCloudPresets = async () => {
    const response = await cloud.get('presets', {
      headers: { Authorization: `Bearer ${localStorage.getItem('jwt')}` }
    })
    if (response.status !== 200) {
      alert('No Access')
      return
    }
    const res = await response.data
    const cEffects = {} as any
    res.forEach((p: { effect: { Name: string } }) => {
      if (!cEffects[p.effect.Name]) cEffects[p.effect.Name] = []
      cEffects[p.effect.Name].push(p)
    })
    setCloudEffects(cEffects)
  }

  const getCloudConfigs = async () => {
    const response = await cloud.get(
      `configs?user.username=${localStorage.getItem('username')}`,
      {
        headers: { Authorization: `Bearer ${localStorage.getItem('jwt')}` }
      }
    )
    if (response.status !== 200) {
      alert('No Access')
      return
    }
    const res = await response.data
    setCloudConfigs(res)
  }

  const getCloudPlaylists = async () => {
    const response = await cloud.get(
      `playlists?user.username=${localStorage.getItem('username')}`,
      {
        headers: { Authorization: `Bearer ${localStorage.getItem('jwt')}` }
      }
    )
    if (response.status !== 200) {
      alert('No Access')
      return
    }
    const res = await response.data
    setCloudPlaylists(res)
  }

  const hasStarred = async () => {
    const r = await fetch(`https://api.github.com/users/${userName}/starred`)
    const re = await r.json()
    const repos = re.map((resp: any) => resp.full_name)
    setStarred({
      core: repos.includes('LedFx/LedFx'),
      client: repos.includes('YeonV/LedFx-Frontend-v2'),
      build: repos.includes('YeonV/LedFx-Builds'),
      hass: repos.includes('YeonV/home-assistant-addons'),
      wledman: repos.includes('YeonV/wled-manager'),
      audiopipes: repos.includes('YeonV/audio-pipes'),
      io: repos.includes('YeonV/io')
    })
  }
  const deleteCloudConfig = async (name: string, date: any) => {
    const existing = await cloud.get(
      `configs?user.username=${localStorage.getItem(
        'username'
      )}&Name=${name}&Date=${date}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('jwt')}`
        }
      }
    )
    const exists = await existing.data
    if (exists.length && exists.length > 0) {
      cloud.delete(`configs/${exists[0].id}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('jwt')}`
        }
      })
    }
  }

  const deleteCloudPlaylist = async (name: string, date: any) => {
    const existing = await cloud.get(
      `configs?user.username=${localStorage.getItem(
        'username'
      )}&Name=${name}&Date=${date}`,
      {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('jwt')}`
        }
      }
    )
    const exists = await existing.data
    if (exists.length && exists.length > 0) {
      cloud.delete(`configs/${exists[0].id}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('jwt')}`
        }
      })
    }
  }

  useEffect(() => {
    if (setTrophies) {
      if (starred.core && starred.client && starred.build) {
        setTrophies((s) => ({ ...s, fan: 1 }))
      } else {
        setTrophies((s) => ({ ...s, fan: 0 }))
      }
      if (starred.hass && starred.wledman && starred.audiopipes && starred.io) {
        setTrophies((s) => ({ ...s, enthusiast: 1 }))
      } else {
        setTrophies((s) => ({ ...s, enthusiast: 0 }))
      }
      if (
        Object.keys(filteredCloudEffects)
          .map((effect) => filteredCloudEffects[effect].length)
          .reduce((a, b) => a + b, 0) > 0
      ) {
        setTrophies((s) => ({ ...s, contributor: 1 }))
      } else {
        setTrophies((s) => ({ ...s, contributor: 0 }))
      }
    }
  }, [starred, cloudEffects, setTrophies])

  useEffect(() => {
    if (isLogged && localStorage.getItem('ledfx-cloud-role') === 'creator') {
      getCloudPresets()
      getCloudPlaylists()
      getCloudConfigs()
    }
    hasStarred()
  }, [])

  useEffect(() => {
    const t = () => {
      if (trophies.contributor > 0) {
        return 4
      }
      if (trophies.enthusiast > 0) {
        return 3
      }
      if (trophies.fan > 0) {
        return 2
      }
      return 0
    }
    setAvailableThemes(t())
  }, [trophies])

  return (
    <Box
      alignItems="center"
      justifyContent="center"
      sx={{ marginBottom: '5rem' }}
    >
      <Stack
        alignItems="center"
        direction="column"
        gap={2}
        maxWidth={450}
        margin="0 auto"
      >
        <Collapse in={infoAlerts.user}>
          <Alert
            sx={{ mb: 2 }}
            severity="error"
            onClose={() => {
              if (localStorage.getItem('ledfx-cloud-role') === 'creator')
                setInfoAlerts('user', false)
            }}
          >
            LedFx Cloud is a proof of concept and is running on a cheap six
            bucks a month server.
            <br />
            Dont expect anything in alpha-state. like if the server crashes the
            data is gone!
            <br />
            <br />
            You have been warned!
          </Alert>
        </Collapse>
        <Stack
          direction="row"
          gap={2}
          maxWidth={450}
          alignItems="center"
          margin="0 auto"
          sx={{
            border: '1px solid',
            borderColor: 'text.disabled',
            borderRadius: '75px',
            padding: '0 3rem 0 0',
            minWidth: 350
          }}
        >
          {localStorage.getItem('ledfx-cloud-role') === 'creator' ? (
            <AvatarPicker storage="cloud" />
          ) : (
            <GitHub sx={{ fontSize: 'min(25vw, 25vh, 150px)' }} />
          )}
          <Stack
            alignItems="center"
            direction="column"
            gap={2}
            maxWidth={450}
            margin="0 auto"
          >
            <Typography variant="h5">
              {userName !== 'YeonV' ? 'FreeUser' : ''}
              &nbsp;{userName}&nbsp;
            </Typography>
            {isLogged ? (
              <Badge
                sx={{ paddingTop: 2 }}
                badgeContent={
                  localStorage.getItem('ledfx-cloud-role') === 'authenticated'
                    ? 'logged in'
                    : localStorage.getItem('ledfx-cloud-role')
                }
                color="primary"
              />
            ) : (
              'Logged out'
            )}
          </Stack>
        </Stack>
        <div style={{ width: 450 }}>
          <Accordion
            expanded={expanded === 'panel0'}
            onChange={handleChange('panel0')}
          >
            <AccordionSummary
              expandIcon={<>&nbsp;</>}
              aria-controls="panel0bh-content"
              id="panel0bh-header"
              sx={{ pointerEvents: 'none' }}
            >
              <Typography sx={{ width: '60%', flexShrink: 0 }}>User</Typography>
              <Typography
                sx={{
                  color: 'text.secondary',
                  textAlign: 'right',
                  flexGrow: 1
                }}
              >
                {userName || ''}
              </Typography>
            </AccordionSummary>
          </Accordion>
          <Accordion
            expanded={expanded === 'panel01'}
            onChange={handleChange('panel01')}
          >
            <AccordionSummary
              expandIcon={<>&nbsp;</>}
              aria-controls="panel01bh-content"
              id="panel01bh-header"
              sx={{ pointerEvents: 'none' }}
            >
              <Typography sx={{ width: '60%', flexShrink: 0 }}>Role</Typography>
              <Typography
                sx={{
                  color: 'text.secondary',
                  textAlign: 'right',
                  flexGrow: 1
                }}
              >
                {localStorage.getItem('ledfx-cloud-role') === 'authenticated'
                  ? 'logged in'
                  : localStorage.getItem('ledfx-cloud-role')}
              </Typography>
            </AccordionSummary>
          </Accordion>
          <Accordion
            expanded={expanded === 'panel001'}
            onChange={handleChange('panel001')}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="panel001bh-content"
              id="panel001bh-header"
            >
              <Typography sx={{ width: '60%', flexShrink: 0 }}>
                Trophies
              </Typography>
              <Typography
                sx={{
                  color: 'text.secondary',
                  textAlign: 'right',
                  flexGrow: 1,
                  paddingRight: 2
                }}
              >
                {trophies.enthusiast + trophies.fan + trophies.contributor}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography variant="caption" color="GrayText">
                earn trophies and unlock features
              </Typography>
              {/**
               *
               *
               *
               *
               */}
              <Accordion
                expanded={subExpanded === 'sub1'}
                onChange={handleChangeSub('sub1')}
                sx={{ padding: 0 }}
                elevation={0}
              >
                <AccordionSummary
                  expandIcon={<ExpandMoreIcon />}
                  aria-controls="sub1bh-content"
                  id="sub1bh-header"
                  sx={{ padding: 0, alignItems: 'center' }}
                >
                  <Typography
                    sx={{
                      width: '60%',
                      flexShrink: 0,
                      alignItems: 'center',
                      display: 'flex'
                    }}
                  >
                    Fan
                  </Typography>
                  <Typography
                    sx={{
                      color: 'text.secondary',
                      textAlign: 'right',
                      flexGrow: 1,
                      paddingRight: 2,
                      alignItems: 'center',
                      display: 'flex',
                      justifyContent: 'flex-end'
                    }}
                  >
                    <EmojiEventsOutlined />
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" align="center">
                    star repos to earn trophy
                  </Typography>
                  <EmojiEventsOutlined
                    sx={{
                      fontSize: 150,
                      width: '100%',
                      alignSelf: 'center',
                      color:
                        trophies.fan > 0
                          ? theme.palette.primary.main
                          : 'inherit'
                    }}
                  />
                  <Box sx={{ width: '100%', zIndex: 1000 }}>
                    <Stepper nonLinear activeStep={1} alternativeLabel>
                      <Step key="core" completed={starred.core}>
                        <StepButton
                          onClick={() => {
                            window.open(
                              'https://github.com/LedFx/LedFx',
                              '_blank'
                            )
                          }}
                          sx={{
                            textTransform: 'capitalize',
                            color: starred.core
                              ? theme.palette.primary.main
                              : 'inherit'
                          }}
                          icon={starred.core ? <Star /> : <StarOutline />}
                        >
                          core
                        </StepButton>
                      </Step>
                      <Step key="client" completed={starred.client}>
                        <StepButton
                          onClick={() => {
                            window.open(
                              'https://github.com/YeonV/LedFx-Frontend-v2',
                              '_blank'
                            )
                          }}
                          sx={{
                            textTransform: 'capitalize',
                            color: starred.client
                              ? theme.palette.primary.main
                              : 'inherit'
                          }}
                          icon={starred.client ? <Star /> : <StarOutline />}
                        >
                          client
                        </StepButton>
                      </Step>
                      <Step key="build" completed={starred.build}>
                        <StepButton
                          onClick={() => {
                            window.open(
                              'https://github.com/YeonV/LedFx-Builds',
                              '_blank'
                            )
                          }}
                          sx={{
                            textTransform: 'capitalize',
                            color: starred.build
                              ? theme.palette.primary.main
                              : 'inherit'
                          }}
                          icon={starred.build ? <Star /> : <StarOutline />}
                        >
                          build
                        </StepButton>
                      </Step>
                    </Stepper>
                  </Box>
                </AccordionDetails>
              </Accordion>
              <Accordion
                expanded={subExpanded === 'sub2'}
                onChange={handleChangeSub('sub2')}
                sx={{ padding: 0, backgroundColor: 'transparent !important' }}
                elevation={0}
              >
                <AccordionSummary
                  expandIcon={<ExpandMoreIcon />}
                  aria-controls="sub2bh-content"
                  id="sub2bh-header"
                  sx={{ padding: 0 }}
                >
                  <Typography
                    sx={{
                      width: '60%',
                      flexShrink: 0,
                      alignItems: 'center',
                      display: 'flex'
                    }}
                  >
                    Enthusiast
                  </Typography>
                  <Typography
                    sx={{
                      color: 'text.secondary',
                      textAlign: 'right',
                      flexGrow: 1,
                      paddingRight: 2,
                      alignItems: 'center',
                      display: 'flex',
                      justifyContent: 'flex-end'
                    }}
                  >
                    <EmojiEventsOutlined />
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ textAlign: 'center' }}>
                  <Typography variant="caption" align="center">
                    star repos to earn trophy
                  </Typography>
                  <EmojiEventsOutlined
                    sx={{
                      fontSize: 150,
                      width: '100%',
                      alignSelf: 'center',
                      color:
                        trophies.enthusiast > 0
                          ? theme.palette.primary.main
                          : 'inherit'
                    }}
                  />
                  <Box sx={{ width: '100%', zIndex: 1000 }}>
                    <Stepper nonLinear activeStep={1} orientation="vertical">
                      <Step key="hass" completed={starred.hass}>
                        <StepButton
                          onClick={() => {
                            window.open(
                              'https://github.com/YeonV/home-assistant-addons',
                              '_blank'
                            )
                          }}
                          sx={{
                            textTransform: 'capitalize',
                            color: starred.hass
                              ? theme.palette.primary.main
                              : 'inherit'
                          }}
                          icon={starred.hass ? <Star /> : <StarOutline />}
                        >
                          home-assistant-addons
                        </StepButton>
                      </Step>
                      <Step key="wledman" completed={starred.wledman}>
                        <StepButton
                          onClick={() => {
                            window.open(
                              'https://github.com/YeonV/wled-manager',
                              '_blank'
                            )
                          }}
                          sx={{
                            textTransform: 'capitalize',
                            color: starred.wledman
                              ? theme.palette.primary.main
                              : 'inherit'
                          }}
                          icon={starred.wledman ? <Star /> : <StarOutline />}
                        >
                          wled-manager
                        </StepButton>
                      </Step>
                      <Step key="audiopipes" completed={starred.audiopipes}>
                        <StepButton
                          onClick={() => {
                            window.open(
                              'https://github.com/YeonV/audio-pipes',
                              '_blank'
                            )
                          }}
                          sx={{
                            textTransform: 'capitalize',
                            color: starred.audiopipes
                              ? theme.palette.primary.main
                              : 'inherit'
                          }}
                          icon={starred.audiopipes ? <Star /> : <StarOutline />}
                        >
                          audio-pipes
                        </StepButton>
                      </Step>
                      <Step key="io" completed={starred.io}>
                        <StepButton
                          onClick={() => {
                            window.open('https://github.com/YeonV/io', '_blank')
                          }}
                          sx={{
                            textTransform: 'capitalize',
                            color: starred.io
                              ? theme.palette.primary.main
                              : 'inherit'
                          }}
                          icon={starred.io ? <Star /> : <StarOutline />}
                        >
                          io
                        </StepButton>
                      </Step>
                    </Stepper>
                  </Box>
                </AccordionDetails>
              </Accordion>
              <Accordion
                expanded={subExpanded === 'sub3'}
                onChange={handleChangeSub('sub3')}
                sx={{ padding: 0, backgroundColor: 'transparent !important' }}
                elevation={0}
              >
                <AccordionSummary
                  expandIcon={<ExpandMoreIcon />}
                  aria-controls="sub3bh-content"
                  id="sub3bh-header"
                  sx={{ padding: 0 }}
                >
                  <Typography
                    sx={{
                      width: '60%',
                      flexShrink: 0,
                      alignItems: 'center',
                      display: 'flex'
                    }}
                  >
                    Contributor
                  </Typography>
                  <Typography
                    sx={{
                      color: 'text.secondary',
                      textAlign: 'right',
                      flexGrow: 1,
                      paddingRight: 2,
                      alignItems: 'center',
                      display: 'flex',
                      justifyContent: 'flex-end'
                    }}
                  >
                    <EmojiEventsOutlined />
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Typography>Create amazing presets and share them</Typography>
                  <EmojiEventsOutlined
                    sx={{
                      fontSize: 150,
                      width: '100%',
                      alignSelf: 'center',
                      color:
                        trophies.contributor > 0
                          ? theme.palette.primary.main
                          : 'inherit'
                    }}
                  />
                </AccordionDetails>
              </Accordion>

              {/**
               *
               *
               *
               *
               */}
            </AccordionDetails>
          </Accordion>
          <Accordion
            expanded={expanded === 'panel1'}
            onChange={handleChange('panel1')}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="panel1bh-content"
              id="panel1bh-header"
            >
              <Typography sx={{ width: '60%', flexShrink: 0 }}>
                Cloud-Presets
              </Typography>
              <Typography
                sx={{
                  color: 'text.secondary',
                  textAlign: 'right',
                  flexGrow: 1,
                  paddingRight: 2
                }}
              >
                {Object.keys(filteredCloudEffects)
                  .map((effect) => filteredCloudEffects[effect].length)
                  .reduce((a, b) => a + b, 0)}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Typography>
                {Object.keys(filteredCloudEffects)
                  .map((effect) => filteredCloudEffects[effect].length)
                  .reduce((a, b) => a + b, 0) === 0
                  ? 'No CloudPresets yet.'
                  : 'Manage your CloudPresets in Device-view'}
              </Typography>
            </AccordionDetails>
          </Accordion>
          <Accordion
            expanded={expanded === 'panel2'}
            onChange={handleChange('panel2')}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="panel2bh-content"
              id="panel2bh-header"
            >
              <Typography sx={{ width: '60%', flexShrink: 0 }}>
                Cloud-Configs
              </Typography>
              <Typography
                sx={{
                  color: 'text.secondary',
                  textAlign: 'right',
                  flexGrow: 1,
                  paddingRight: 2
                }}
              >
                {cloudConfigs.length}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
              >
                <Typography>Upload current config</Typography>
                <Popover
                  icon={<CloudUpload />}
                  disabled={cloudConfigs.length >= 5}
                  type="iconbutton"
                  color="inherit"
                  confirmDisabled={configName === ''}
                  onConfirm={() => {
                    getFullConfig().then((c: any) =>
                      cloud
                        .post(
                          'configs',
                          {
                            Name: configName,
                            Date: +new Date(),
                            config: c,
                            user: localStorage.getItem('ledfx-cloud-userid')
                          },
                          {
                            headers: {
                              Authorization: `Bearer ${localStorage.getItem(
                                'jwt'
                              )}`
                            }
                          }
                        )
                        .then(() => getCloudConfigs())
                    )
                  }}
                  content={
                    <TextField
                      value={configName}
                      onChange={(e) => setConfigName(e.target.value)}
                      placeholder="Enter Config Name"
                    />
                  }
                />
              </Stack>
              {cloudConfigs.length > 0 &&
                cloudConfigs.map((c: any, i: number) => (
                  <div key={i}>
                    <Divider />
                    <Stack
                      direction="row"
                      justifyContent="space-between"
                      alignItems="center"
                    >
                      <Typography>{c.Name}</Typography>

                      <Stack direction="row" alignItems="center">
                        <Popover
                          type="iconbutton"
                          color="inherit"
                          onConfirm={() =>
                            deleteCloudConfig(c.Name, c.Date).then(() =>
                              setTimeout(() => {
                                getCloudConfigs()
                              }, 200)
                            )
                          }
                        />
                        {/* <Tooltip title="Load Config"> */}
                        <Popover
                          onConfirm={() => {
                            const { user_presets } = c.config
                            setSystemConfig({ user_presets }).then(() => {
                              window.location.href = window.location.href
                            })
                          }}
                          content={
                            <Stack>
                              <Typography
                                sx={{ padding: '0.5rem 1rem 0 1rem' }}
                              >
                                overwrite current config?
                              </Typography>
                              <Typography
                                color="text.disabled"
                                sx={{ padding: '0 1rem 0.5rem 1rem' }}
                              >
                                LedFx will restart after
                              </Typography>
                            </Stack>
                          }
                          type="iconbutton"
                          color="inherit"
                          icon={
                            <Tooltip title="Import Presets from Config">
                              <Tune />
                            </Tooltip>
                          }
                        />
                        <Popover
                          onConfirm={() => {
                            importSystemConfig(c.config).then(() => {
                              window.location.href = window.location.href
                            })
                          }}
                          content={
                            <Stack>
                              <Typography
                                sx={{ padding: '0.5rem 1rem 0 1rem' }}
                              >
                                overwrite current config?
                              </Typography>
                              <Typography
                                color="text.disabled"
                                sx={{ padding: '0 1rem 0.5rem 1rem' }}
                              >
                                LedFx will restart after
                              </Typography>
                            </Stack>
                          }
                          type="iconbutton"
                          color="inherit"
                          icon={
                            <Tooltip title="Load Config">
                              <CloudDownload />
                            </Tooltip>
                          }
                        />
                        {/* </Tooltip> */}

                        <Tooltip
                          title={`Config from ${new Intl.DateTimeFormat(
                            'en-GB',
                            {
                              dateStyle: 'medium',
                              timeStyle: 'medium'
                            }
                          )
                            .format(new Date(c.Date))
                            .split(',')
                            .join(' at ')}`}
                        >
                          <AccessTime sx={{ marginLeft: 1 }} />
                        </Tooltip>
                      </Stack>
                    </Stack>
                  </div>
                ))}
            </AccordionDetails>
          </Accordion>

          <Accordion
            expanded={expanded === 'panel3'}
            onChange={handleChange('panel3')}
          >
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="panel3bh-content"
              id="panel3bh-header"
            >
              <Typography sx={{ width: '60%', flexShrink: 0 }}>
                Cloud-Playlists
              </Typography>
              <Typography
                sx={{
                  color: 'text.secondary',
                  textAlign: 'right',
                  flexGrow: 1,
                  paddingRight: 2
                }}
              >
                {cloudPlaylists.length}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack
                direction="row"
                justifyContent="space-between"
                alignItems="center"
              >
                <Typography>Upload current playlist</Typography>
                <Popover
                  icon={<CloudUpload />}
                  disabled={cloudPlaylists.length >= 5}
                  type="iconbutton"
                  color="inherit"
                  confirmDisabled={playlistName === ''}
                  onConfirm={() => {
                    cloud
                      .post(
                        'playlists',
                        {
                          Name: playlistName,
                          Date: +new Date(),
                          playlist: scenePL,
                          user: localStorage.getItem('ledfx-cloud-userid')
                        },
                        {
                          headers: {
                            Authorization: `Bearer ${localStorage.getItem(
                              'jwt'
                            )}`
                          }
                        }
                      )
                      .then(() => getCloudPlaylists())
                  }}
                  content={
                    <TextField
                      value={playlistName}
                      onChange={(e) => setPlaylistName(e.target.value)}
                      placeholder="Enter Playlist Name"
                    />
                  }
                />
              </Stack>
              {cloudPlaylists.length > 0 &&
                cloudPlaylists.map((p: any, i: number) => (
                  <div key={i}>
                    <Divider />
                    <Stack
                      direction="row"
                      justifyContent="space-between"
                      alignItems="center"
                    >
                      <Typography>{p.Name}</Typography>

                      <Stack direction="row" alignItems="center">
                        <Popover
                          type="iconbutton"
                          color="inherit"
                          onConfirm={() =>
                            deleteCloudPlaylist(p.Name, p.Date).then(() =>
                              setTimeout(() => {
                                getCloudPlaylists()
                              }, 200)
                            )
                          }
                        />
                        <Popover
                          onConfirm={() => {
                            setScenePL(p.playlist)
                          }}
                          content={
                            <Stack>
                              <Typography
                                sx={{ padding: '0.5rem 1rem 0 1rem' }}
                              >
                                overwrite current playlist?
                              </Typography>
                            </Stack>
                          }
                          type="iconbutton"
                          color="inherit"
                          icon={
                            <Tooltip title="Load Playlist">
                              <CloudDownload />
                            </Tooltip>
                          }
                        />

                        <Tooltip
                          title={`Config from ${new Intl.DateTimeFormat(
                            'en-GB',
                            {
                              dateStyle: 'medium',
                              timeStyle: 'medium'
                            }
                          )
                            .format(new Date(p.Date))
                            .split(',')
                            .join(' at ')}`}
                        >
                          <AccessTime sx={{ marginLeft: 1 }} />
                        </Tooltip>
                      </Stack>
                    </Stack>
                  </div>
                ))}
            </AccordionDetails>
          </Accordion>

          {(trophies.fan > 0 ||
            trophies.enthusiast > 0 ||
            trophies.contributor > 0) && (
            <Accordion
              expanded={expanded === 'panel4'}
              onChange={handleChange('panel4')}
            >
              <AccordionSummary
                expandIcon={<ExpandMoreIcon />}
                aria-controls="panel4bh-content"
                id="panel4bh-header"
              >
                <Typography sx={{ width: '60%', flexShrink: 0 }}>
                  Theme-Selector
                </Typography>
                <Typography
                  sx={{
                    color: 'text.secondary',
                    textAlign: 'right',
                    flexGrow: 1,
                    paddingRight: 2
                  }}
                >
                  {availableThemes}
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Select
                  value={
                    window.localStorage.getItem('ledfx-theme') || 'DarkBlue'
                  }
                  fullWidth
                  onChange={(e) => {
                    if (e.target.value === 'DarkBlue') {
                      window.localStorage.setItem('ledfx-theme', 'DarkBlue')
                      window.location.reload()
                    } else if (e.target.value === 'DarkOrange') {
                      window.localStorage.setItem('ledfx-theme', 'DarkOrange')
                      window.location.reload()
                    } else if (e.target.value === 'DarkGreen') {
                      window.localStorage.setItem('ledfx-theme', 'DarkGreen')
                      window.location.reload()
                    } else if (e.target.value === 'DarkRed') {
                      window.localStorage.setItem('ledfx-theme', 'DarkRed')
                      window.location.reload()
                    }
                  }}
                >
                  <MenuItem value="DarkBlue">Blade&apos;s Blue</MenuItem>
                  <MenuItem value="DarkOrange">Blade&apos;s Orange</MenuItem>
                  {(trophies.enthusiast > 0 || trophies.contributor > 0) && (
                    <MenuItem value="DarkGreen">Blade&apos;s Green</MenuItem>
                  )}
                  {trophies.contributor > 0 && (
                    <MenuItem value="DarkRed">Blade&apos;s Red</MenuItem>
                  )}
                </Select>
              </AccordionDetails>
            </Accordion>
          )}
        </div>
      </Stack>
    </Box>
  )
}

export default User

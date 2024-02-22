/* eslint-disable no-alert */
/* eslint-disable consistent-return */
/* eslint-disable no-restricted-syntax */
/* eslint-disable @typescript-eslint/no-empty-function */
import { useEffect, useState } from 'react'
import { useTheme } from '@mui/material/styles'
import {
  AppBar,
  Button,
  Card,
  CardHeader,
  Dialog,
  Grid,
  IconButton,
  ListItemIcon,
  Toolbar,
  Typography
} from '@mui/material'
import { Settings, NavigateBefore, CloudDownload } from '@mui/icons-material'
import useEditVirtualsStyles from '../../Devices/EditVirtuals/EditVirtuals.styles'
import useStore from '../../../store/useStore'

import { cloud, Transition, MuiMenuItem } from './CloudComponents'

export default function CloudScreen({
  virtId,
  effectType,
  icon = <Settings />,
  startIcon,
  label = '',
  type,
  className,
  color = 'inherit',
  variant = 'contained',
  onClick = () => {},
  innerKey
}: any) {
  const classes = useEditVirtualsStyles()
  const theme = useTheme()
  const [open, setOpen] = useState(false)
  const [cloudEffects, setCloudEffects] = useState<any>([])
  const [activeCloudPreset, setActiveCloudPreset] = useState()
  const setEffect = useStore((state) => state.setEffect)
  const addPreset = useStore((state) => state.addPreset)
  const getPresets = useStore((state) => state.getPresets)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const virtuals = useStore((state) => state.virtuals)
  const getV = () => {
    for (const prop in virtuals) {
      if (virtuals[prop].id === virtId) {
        return virtuals[prop]
      }
    }
  }

  const virtual = getV()

  const handleClickOpen = () => {
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
  }

  const refreshPresets = async () => {
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
      if (!cEffects[p.effect.Name]) {
        cEffects[p.effect.Name] = []
      }
      cEffects[p.effect.Name].push(p)
    })
    setCloudEffects(cEffects)
  }

  const handleCloudPresets = async (p: any, save: boolean) => {
    setActiveCloudPreset(p.Name.toLowerCase())
    if (p.effect.ledfx_id !== effectType) {
      await setEffect(virtId, p.effect.ledfx_id, {}, false)
      await getVirtuals()
    }
    await setEffect(virtId, p.effect.ledfx_id, p.config, true)
    if (save) {
      await addPreset(virtId, p.Name)
      await getPresets(p.effect.ledfx_id)
    }
    await getVirtuals()
  }

  useEffect(() => {
    refreshPresets()
  }, [])

  // console.log(virtual.effect.name, Object.keys(cloudEffects)

  return (
    <>
      {type === 'menuItem' ? (
        <MuiMenuItem
          key={innerKey}
          className={className}
          onClick={(e: any) => {
            e.preventDefault()
            onClick(e)
            handleClickOpen()
          }}
        >
          <ListItemIcon>{icon}</ListItemIcon>
          {label}
        </MuiMenuItem>
      ) : (
        <Button
          variant={variant}
          startIcon={startIcon}
          color={color}
          onClick={(e) => {
            onClick(e)
            refreshPresets()
            handleClickOpen()
          }}
          size="small"
          style={{ padding: '2px 15px', marginRight: '0.4rem' }}
          className={className}
        >
          {label}
          {!startIcon && icon}
        </Button>
      )}
      <Dialog
        fullScreen
        open={open}
        onClose={handleClose}
        TransitionComponent={Transition}
      >
        <AppBar enableColorOnDark className={classes.appBar}>
          <Toolbar>
            <Button
              color="primary"
              variant="contained"
              startIcon={<NavigateBefore />}
              onClick={handleClose}
            >
              back
            </Button>
            <Typography variant="h6" className={classes.title}>
              LedFx Cloud
            </Typography>
          </Toolbar>
        </AppBar>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {Object.keys(cloudEffects).map((effect, i) => (
            <div
              key={i}
              style={{
                order:
                  virtual?.effect.name.toLowerCase() === effect.toLowerCase()
                    ? -1
                    : 1
              }}
            >
              <Typography
                className={classes.segmentTitle}
                variant="caption"
                style={{
                  color:
                    virtual?.effect.name.toLowerCase() === effect.toLowerCase()
                      ? theme.palette.primary.main
                      : theme.palette.text.primary
                }}
              >
                {effect}
              </Typography>
              <Grid style={{ padding: 20 }} container spacing={2}>
                {cloudEffects[effect].map((p: any, ind: number) => (
                  <Grid item key={ind}>
                    <Card
                      className={`${classes.cloudEffectCard} ${
                        virtual?.effect.name.toLowerCase() ===
                          effect.toLowerCase() &&
                        activeCloudPreset === p.Name.toLowerCase()
                          ? ' active'
                          : ''
                      }`}
                      key={ind}
                      onClick={() => handleCloudPresets(p, false)}
                    >
                      <CardHeader
                        title={p.Name}
                        subheader={
                          <div
                            style={{ color: '#999' }}
                          >{`by ${p.user.username}`}</div>
                        }
                        action={
                          <IconButton
                            aria-label="Import"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleCloudPresets(p, true)
                            }}
                          >
                            <CloudDownload />
                          </IconButton>
                        }
                      />
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </div>
          ))}
        </div>
      </Dialog>
    </>
  )
}

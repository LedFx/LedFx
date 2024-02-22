import { useState, useEffect } from 'react'
import { useTheme } from '@mui/material/styles'
import Card from '@mui/material/Card'
import Button from '@mui/material/Button'
import SettingsIcon from '@mui/icons-material/Settings'
import VisibilityIcon from '@mui/icons-material/Visibility'
import TuneIcon from '@mui/icons-material/Tune'
import BuildIcon from '@mui/icons-material/Build'
import { NavLink } from 'react-router-dom'
import Collapse from '@mui/material/Collapse'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import IconButton from '@mui/material/IconButton'
import Typography from '@mui/material/Typography'
import {
  Clear,
  Delete,
  Pause,
  PlayArrow,
  SyncProblem
} from '@mui/icons-material'
import { Box } from '@mui/material'
import Popover from '../../../components/Popover/Popover'
import EditVirtuals from '../EditVirtuals/EditVirtuals'
import PixelGraph from '../../../components/PixelGraph'
import BladeIcon from '../../../components/Icons/BladeIcon/BladeIcon'
import useStyle from './DeviceCard.styles'
import { DeviceCardDefaults, DeviceCardProps } from './DeviceCard.interface'

/**
 * Pixelgraphs will not connect via Websocket in Storybook
 *
 */
const DeviceCard = ({
  deviceName,
  online,
  virtId,
  index,
  handleDeleteDevice,
  handleEditVirtual,
  handleEditDevice,
  handleClearEffect,
  handlePlayPause,
  linkTo,
  additionalStyle,
  iconName,
  graphsActive,
  colorIndicator,
  effectName,
  isPlaying,
  isStreaming,
  previewOnly,
  isEffectSet,
  transitionTime,
  isDevice,
  graphsMulti,
  showMatrix,
  activateDevice
}: DeviceCardProps) => {
  const classes = useStyle()
  const theme = useTheme()
  // eslint-disable-next-line
  const [fade, _setFade] = useState(false);
  const [isActive, setIsActive] = useState(isEffectSet || isStreaming)

  const [expanded, setExpanded] = useState(false)
  const color = 'inherit'

  const handleExpandClick = () => {
    setExpanded(!expanded)
  }

  useEffect(() => {
    setIsActive(isEffectSet || isStreaming)
  }, [isEffectSet, isStreaming])

  return (
    <NavLink
      to={linkTo}
      className={`${classes.virtualCardPortraitW} ${
        isEffectSet ? 'active' : ''
      } ${online ? 'online' : 'offline'}`}
      style={{
        ...additionalStyle,
        width: '100%',
        background: theme.palette.background.paper
      }}
    >
      <Card
        className={classes.virtualCardPortrait}
        sx={{
          background: theme.palette.background.paper,
          '&:hover': {
            borderColor: theme.palette.text.disabled
          }
        }}
      >
        <div className={classes.virtualCardContainer}>
          <div className={classes.virtualIconWrapper}>
            <BladeIcon
              colorIndicator={false}
              name={iconName}
              className={`${classes.virtualIcon} ${
                !graphsActive ? 'graphs' : ''
              } ${expanded ? 'extended' : ''}`}
              style={{
                zIndex: 3,
                opacity: online ? 1 : 0.3,
                color: expanded ? '#fff' : ''
              }}
              card
            />
          </div>

          <div className={classes.virtualSubline}>
            <Typography
              variant="h6"
              style={{
                lineHeight: 1,
                color: colorIndicator ? theme.palette.primary.light : 'inherit',
                opacity: online ? 1 : 0.3
              }}
            >
              {deviceName}
            </Typography>
            {!online ? (
              <Typography
                variant="body1"
                color="textSecondary"
                style={{
                  height: 25,
                  display: 'flex',
                  alignItems: 'center'
                }}
              >
                <Typography
                  variant="body1"
                  component="span"
                  color="textSecondary"
                  style={{
                    height: 25,
                    opacity: online ? 1 : 0.3
                  }}
                >
                  offline
                </Typography>
                <Button
                  variant="text"
                  size="small"
                  onClick={(e) => {
                    e.preventDefault()
                    if (isDevice) {
                      activateDevice(isDevice)
                    }
                  }}
                  style={{
                    color: 'inherit',
                    marginLeft: '1rem',
                    marginTop: '0rem',
                    minWidth: 'unset',
                    zIndex: expanded ? 1 : 3
                  }}
                >
                  <SyncProblem />
                </Button>
              </Typography>
            ) : effectName ? (
              <Typography
                variant="body1"
                color="textSecondary"
                style={{ height: 25, display: 'flex', alignItems: 'center' }}
              >
                <span className="hideMobile">Effect:&nbsp;</span>
                {effectName}
                <Button
                  variant="text"
                  size="small"
                  onClick={(e) => {
                    e.preventDefault()
                    handlePlayPause()
                  }}
                  style={{
                    color: '#999',
                    minWidth: 'unset',
                    zIndex: expanded ? 1 : 3
                  }}
                >
                  {isPlaying ? <Pause /> : <PlayArrow />}
                </Button>
                <Button
                  size="small"
                  variant="text"
                  onClick={(e) => {
                    e.preventDefault()
                    handleClearEffect(virtId)
                  }}
                  style={{
                    color: '#999',
                    minWidth: 'unset',
                    zIndex: expanded ? 1 : 3
                  }}
                >
                  <Clear />
                </Button>
              </Typography>
            ) : isStreaming ? (
              <Typography
                variant="body1"
                color="textSecondary"
                style={{ height: 25 }}
              >
                Streaming...
              </Typography>
            ) : (
              <Typography
                variant="body1"
                style={{ color: theme.palette.text.disabled, height: 25 }}
              >
                off
              </Typography>
            )}
          </div>

          <div>
            {previewOnly && (
              <Button variant="text" disabled size="small">
                <VisibilityIcon />
              </Button>
            )}
          </div>

          {!(window.localStorage.getItem('guestmode') === 'activated') ? (
            <IconButton
              sx={{
                transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                alignSelf: 'flex-start',
                marginLeft: 'auto',
                transition: theme.transitions.create('transform', {
                  duration: theme.transitions.duration.shortest
                }),
                display: 'block'
              }}
              onClick={(e) => {
                e.preventDefault()
                handleExpandClick()
              }}
              aria-expanded={expanded}
              aria-label="show more"
              style={{ zIndex: 3, color: '#999' }}
            >
              <ExpandMoreIcon className={`step-devices-two-${index}`} />
            </IconButton>
          ) : (
            <Box
              sx={{
                alignSelf: 'flex-start',
                marginLeft: 'auto',
                display: 'block'
              }}
            />
          )}
        </div>
        {graphsMulti && (
          <div
            style={{
              opacity: fade ? 0.2 : 1,
              transitionDuration: fade
                ? `${transitionTime || 1}s`
                : `${transitionTime || 0}s`,
              width: '100%',
              transition: 'opacity'
            }}
          >
            <PixelGraph
              showMatrix={showMatrix}
              intGraphs={graphsActive}
              active={isActive}
              virtId={virtId || ''}
              className="step-devices-seven"
            />
          </div>
        )}
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            right: 0,
            zIndex: 2
          }}
        >
          <Collapse
            in={expanded}
            timeout="auto"
            unmountOnExit
            className={classes.buttonBarMobile}
          >
            {/* eslint-disable-next-line */}
            <div
              className={`${classes.buttonBarMobileWrapper} ${
                !graphsActive ? 'graphs' : ''
              } ${expanded ? 'extended' : ''}`}
              onClick={(e) => e.preventDefault()}
            >
              <div />
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-end',
                  justifyContent: 'center'
                }}
              >
                <Popover
                  variant="text"
                  startIcon={<Delete />}
                  label="delete"
                  color={color}
                  onConfirm={() => {
                    handleDeleteDevice(virtId)
                    handleExpandClick()
                  }}
                  className={`step-devices-three-${index}`}
                  style={{ width: '100%' }}
                />

                {isDevice ? (
                  <Button
                    variant="text"
                    color={color}
                    size="small"
                    startIcon={<BuildIcon />}
                    className={`step-devices-four-${index}`}
                    onClick={(e) => {
                      e.preventDefault()
                      handleEditDevice(isDevice)
                      handleExpandClick()
                    }}
                  >
                    Edit Device
                  </Button>
                ) : (
                  <EditVirtuals
                    label="Edit Virtual"
                    variant="text"
                    color={color}
                    virtId={virtId}
                    icon={undefined}
                    className="step-devices-six"
                    startIcon={<TuneIcon />}
                    type={undefined}
                    innerKey={undefined}
                    onClick={() => handleExpandClick()}
                  />
                )}
                <Button
                  variant="text"
                  size="small"
                  startIcon={<SettingsIcon />}
                  color={color}
                  className={`step-devices-five-${index}`}
                  onClick={(e) => {
                    e.preventDefault()
                    handleEditVirtual(virtId)
                    handleExpandClick()
                  }}
                >
                  Settings
                </Button>
              </div>
            </div>
          </Collapse>
        </div>
      </Card>
    </NavLink>
  )
}

DeviceCard.defaultProps = DeviceCardDefaults

export default DeviceCard

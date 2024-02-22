/* eslint-disable react/no-danger */
import { Icon } from '@mui/material'
import Wled from '../Wled'
import RazerMouse from '../RzrMouse'
import RazerLogo from '../RzrLogo'
import {
  YZLogo2,
  YZLogo2Bottom,
  YZLogo2Top,
  YZLogo2Y,
  YZLogo2Z
} from '../YZ-Logo2'
import {
  YZLogo3,
  YZLogo3Left,
  YZLogo3Right,
  YZLogo3Top,
  YZLogo3Y,
  YZLogo3Z
} from '../YZ-Logo3'
import { camelToSnake } from '../../../utils/helpers'
import '../../../assets/materialdesignicons.css'
import '../../../index.css'
import { BladeIconDefaultProps, BladeIconProps } from './BladeIcon.interface'
import HomeAssistantLogo from '../HomeAssistant'
import NovationLogo from '../Novation'

/**
 * Icon component supporting 2 libraries
 *
 *  ### [mui](https://mui.com/components/material-icons/)
 *  syntax: `MusicNote`
 *
 *  ### [mdi](https://materialdesignicons.com/)
 *  syntax: `mdi:led-strip` (compatible with home-assistant)
 */
function BladeIcon({
  colorIndicator = false,
  name = 'MusicNote',
  className = '',
  style,
  scene = false,
  card = false,
  intro = false
}: BladeIconProps): JSX.Element {
  return (
    <Icon
      className={className}
      color={colorIndicator ? 'primary' : 'inherit'}
      style={style}
    >
      {name.startsWith('yz:logo2y') ? (
        <YZLogo2Y
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('<svg') ? (
        <div
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
          dangerouslySetInnerHTML={{ __html: name }}
        />
      ) : name.startsWith('https://') ? (
        <img
          src={name.replaceAll('#000000', 'currentColor')}
          width={50}
          alt="icon"
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo2z') ? (
        <YZLogo2Z
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo2top') ? (
        <YZLogo2Top
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo2bot') ? (
        <YZLogo2Bottom
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo2') ? (
        <YZLogo2
          style={{
            // eslint-disable-next-line prettier/prettier
            transform: card ? 'unset' : scene ? 'scale(1)' : intro ? 'scale(0.05)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo3y') ? (
        <YZLogo3Y
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo3z') ? (
        <YZLogo3Z
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo3top') ? (
        <YZLogo3Top
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo3left') ? (
        <YZLogo3Left
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo3right') ? (
        <YZLogo3Right
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('yz:logo3') ? (
        <YZLogo3
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px'
          }}
        />
      ) : name.startsWith('wled') ? (
        <Wled />
      ) : name.startsWith('razer:mouse') ? (
        <RazerMouse />
      ) : name.startsWith('razer:logo') ? (
        <RazerLogo />
      ) : name.startsWith('homeAssistant') ? (
        <HomeAssistantLogo />
      ) : name.startsWith('launchpad') ? (
        <NovationLogo />
      ) : name.startsWith('mdi:') ? (
        <span
          style={{ position: 'relative', display: 'flex' }}
          className={`mdi mdi-${name.split('mdi:')[1]}`}
        />
      ) : (
        name && camelToSnake(name)
      )}
      {/* {name.startsWith('yz:logo2y') ? (
        <YZLogo2Y
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px',
          }}
        />
      ) : name.startsWith('yz:logo2z') ? (
        <YZLogo2Z
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px',
          }}
        />
      ) : name.startsWith('yz:logo2top') ? (
        <YZLogo2Top
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px',
          }}
        />
      ) : name.startsWith('yz:logo2bot') ? (
        <YZLogo2Bottom
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px',
          }}
        />
      ) : name.startsWith('yz:logo2') ? (
        <YZLogo2
          style={{
            transform: card ? 'unset' : scene ? 'scale(1)' : 'scale(0.012)',
            marginTop: '3px',
          }}
        />
      ) : name.startsWith('wled') ? (
        <Wled />
      ) : name.startsWith('razer:mouse') ? (
        <RazerMouse />
      ) : name.startsWith('razer:logo') ? (
        <RazerLogo />
      ) : name.startsWith('mdi:') ? (
        <span
          style={{ position: 'relative', display: 'flex' }}
          className={`mdi mdi-${name.split('mdi:')[1]}`}
        />
      ) : (
        name && camelToSnake(name)
      )} */}
    </Icon>
  )
}

BladeIcon.defaultProps = BladeIconDefaultProps

export default BladeIcon

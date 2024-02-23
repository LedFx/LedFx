import { Button, useMediaQuery } from '@mui/material'
import useStore from '../../store/useStore'

const BladeScene = ({ onClick }: { onClick: () => void }) => {
  const vs = useStore((state) => state.virtuals)
  const autogenerating = Object.keys(vs)
    .filter((v: any) => vs[v].auto_generated)
    .map((vi: any) => vs[vi].segments[0][0])
    .filter((value, index, array) => array.indexOf(value) === index)
  const virtuals: any = Object.keys(vs)
    .filter((v: any) => autogenerating.indexOf(v) === -1)
    .reduce((obj, key) => {
      return {
        ...obj,
        [key]: vs[key]
      }
    }, {})

  const setEffect = useStore((state) => state.setEffect)
  // const updateEffect = useStore((state) => state.updateEffect)
  const activatePreset = useStore((state) => state.activatePreset)
  const addScene = useStore((state) => state.addScene)
  const small = useMediaQuery('(max-width: 720px)')

  const matrix = Object.keys(virtuals).filter(
    (v: string) => virtuals[v].config.rows > 1
  )
  const smalls = Object.keys(virtuals).filter(
    (v: string) => virtuals[v].pixel_count < 9
  )
  const medium = Object.keys(virtuals).filter(
    (v: string) => virtuals[v].pixel_count >= 9 && virtuals[v].pixel_count < 100
  )
  const large = Object.keys(virtuals).filter(
    (v: string) => virtuals[v].pixel_count >= 100
  )

  const addBladeScene = () => {
    // if (noAuto) {
    large.map((v) => {
      setEffect(v, 'melt', {}, true)
      return activatePreset(v, 'ledfx_presets', 'melt', 'purple-red')
    })
    medium.map((v, _i) => {
      setEffect(v, 'blade_power_plus', {}, true)
      // if (_i % 2 === 0)
      //   updateEffect(v, 'blade_power_plus', { flip: true }, false)
      return activatePreset(
        v,
        'ledfx_presets',
        'blade_power_plus',
        'purplered-bass'
      )
    })

    smalls.map((v) => {
      setEffect(v, 'blade_power_plus', {}, true)
      return activatePreset(
        v,
        'ledfx_presets',
        'blade_power_plus',
        'orange-hi-hat'
      )
    })
    // Use medium as smalls
    if (Object.keys(smalls).length === 0 && Object.keys(medium).length > 1) {
      const v = medium.sort(
        (a, b) => virtuals[a].pixel_count - virtuals[b].pixel_count
      )[0]
      setEffect(v, 'blade_power_plus', {}, true)
      activatePreset(v, 'ledfx_presets', 'blade_power_plus', 'orange-hi-hat')
    }
    // Use medium as large
    if (Object.keys(large).length === 0 && Object.keys(medium).length > 2) {
      const v = medium.sort(
        (a, b) => virtuals[a].pixel_count - virtuals[b].pixel_count
      )[Object.keys(medium).length - 1]
      setEffect(v, 'melt', {}, true)
      activatePreset(v, 'ledfx_presets', 'melt', 'purple-red')
    }

    // Use large as smalls
    if (Object.keys(smalls).length === 0 && Object.keys(large).length > 1) {
      const v = large.sort(
        (a, b) => virtuals[a].pixel_count - virtuals[b].pixel_count
      )[0]
      setEffect(v, 'blade_power_plus', {}, true)
      activatePreset(v, 'ledfx_presets', 'blade_power_plus', 'orange-hi-hat')
    }
    // Use large as medium
    if (Object.keys(medium).length === 0 && Object.keys(large).length > 2) {
      const v = large.sort(
        (a, b) => virtuals[a].pixel_count - virtuals[b].pixel_count
      )[1]
      setEffect(v, 'blade_power_plus', {}, true)
      activatePreset(v, 'ledfx_presets', 'blade_power_plus', 'purplered-bass')
    }
    if (Object.keys(matrix).length > 0) {
      matrix.map((v) => {
        return setEffect(
          v,
          'equalizer',
          { gradient_repeat: virtuals[v].config.rows },
          true
        )
      })
    }
    // }
    addScene('Blade Scene', 'yz:logo2', '', '', '', '')
  }

  return (
    <Button
      onClick={() => {
        addBladeScene()
        onClick()
      }}
      sx={{
        borderRadius: '3rem',
        textTransform: 'none',
        marginRight: small ? 0 : '1rem',
        width: small ? '80vw' : 'min(40vw, 550px)',
        fontSize: '2rem'
      }}
    >
      Add Blade Scene
    </Button>
  )
}

export default BladeScene

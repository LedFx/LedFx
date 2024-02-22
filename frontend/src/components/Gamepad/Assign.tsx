import {
  Fab,
  FormControl,
  MenuItem,
  Select,
  Stack,
  useTheme
} from '@mui/material'
import {
  BrightnessHigh,
  BrightnessLow,
  Collections,
  CopyAll,
  GraphicEq,
  LocalPlay,
  PlayArrow,
  QuestionMark,
  SportsEsports,
  Wallpaper
} from '@mui/icons-material'
import useStore from '../../store/useStore'
import BladeIcon from '../Icons/BladeIcon/BladeIcon'
import OneShot from './OneShot'

const Assign = ({
  mapping,
  setMapping,
  pressed,
  index,
  padIndex,
  disabled
}: any) => {
  const theme = useTheme()
  const scenes = useStore((state) => state.scenes)
  const commands = {
    scene: <Wallpaper />,
    smartbar: <LocalPlay />,
    'play/pause': <PlayArrow />,
    'brightness-up': <BrightnessHigh />,
    'brightness-down': <BrightnessLow />,
    'copy-to': <CopyAll />,
    transitions: <GraphicEq />,
    frequencies: <BladeIcon name="mdi:sine-wave" />,
    'scene-playlist': <Collections />,
    padscreen: <SportsEsports />,
    'one-shot': <BladeIcon name="mdi:pistol" />,
    'scan-wled': <BladeIcon name="wled" />
  }

  return (
    <Stack key={index} direction="row" alignItems="center" spacing={1}>
      <Fab
        size="small"
        color={pressed ? 'primary' : 'inherit'}
        sx={{
          background: pressed ? theme.palette.primary.main : '#333',
          m: 1,
          color: disabled ? '#999' : 'inherit',
          width: 40,
          height: 40,
          flexShrink: 0,
          pointerEvents: 'none'
        }}
      >
        {index}
      </Fab>
      <FormControl fullWidth>
        <Select
          fullWidth
          disableUnderline
          disabled={disabled}
          // IconComponent={() => null}
          style={{
            color:
              mapping[padIndex][index]?.command &&
              mapping[padIndex][index]?.command !== 'none'
                ? 'white'
                : 'grey'
          }}
          sx={{
            '& .MuiSelect-select': {
              marginTop: '3px'
            }
          }}
          labelId="command-select-label"
          label="command"
          // renderValue={(v) =>
          //   v === 'scene' ? <Wallpaper sx={{ pr: 4 }} /> : v
          // }
          value={mapping[padIndex][index]?.command || 'none'}
          onChange={(e) =>
            setMapping({
              ...mapping,
              [padIndex]: {
                ...mapping[padIndex],
                [index]: { command: e.target.value }
              }
            })
          }
        >
          <MenuItem value="none" key="none">
            <Stack direction="row" spacing={1}>
              <QuestionMark />
              <span>{disabled ? 'used by LedFx' : 'choose command'}</span>
            </Stack>
          </MenuItem>
          {Object.keys(commands).map((s) => (
            <MenuItem key={s} value={s}>
              <Stack direction="row" spacing={1}>
                {commands[s as keyof typeof commands] || ''}
                <span>{s || 'none'}</span>
              </Stack>
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {mapping[padIndex][index]?.command === 'scene' && (
        <FormControl sx={{ maxWidth: 150 }} fullWidth>
          <Select
            fullWidth
            disableUnderline
            disabled={disabled}
            // IconComponent={() => null}
            style={{
              color:
                mapping[padIndex][index]?.payload &&
                mapping[padIndex][index]?.payload !== 'choose scene'
                  ? 'white'
                  : 'grey'
            }}
            sx={{
              '& .MuiSelect-select': {
                // paddingRight: '0 !important',
                marginTop: '3px'
              }
            }}
            labelId="scene-select-label"
            label="Scene"
            value={mapping[padIndex][index]?.payload?.scene || 'none'}
            onChange={(e) =>
              setMapping({
                ...mapping,
                [padIndex]: {
                  ...mapping[padIndex],
                  [index]: {
                    ...mapping[padIndex][index],
                    payload: { scene: e.target.value }
                  }
                }
              })
            }
          >
            <MenuItem value="none" key="none">
              {disabled ? 'used by LedFx' : 'choose scene'}
            </MenuItem>
            {Object.keys(scenes).map((s: string) => (
              <MenuItem key={s} value={s}>
                {scenes[s]?.name || s || 'none'}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      {mapping[padIndex][index]?.command === 'one-shot' && (
        <OneShot
          defaultColor={mapping[padIndex][index]?.payload?.color}
          defaultRamp={mapping[padIndex][index]?.payload?.ramp}
          defaultFate={mapping[padIndex][index]?.payload?.fade}
          defaultHold={mapping[padIndex][index]?.payload?.hold}
          setPayload={(v: any) =>
            setMapping({
              ...mapping,
              [padIndex]: {
                ...mapping[padIndex],
                [index]: {
                  ...mapping[padIndex][index],
                  payload: v
                }
              }
            })
          }
        />
      )}
    </Stack>
  )
}

export default Assign

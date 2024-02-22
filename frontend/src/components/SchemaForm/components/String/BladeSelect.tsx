/* eslint-disable @typescript-eslint/indent */
import {
  Select,
  MenuItem,
  TextField,
  InputAdornment,
  Button,
  Tooltip
} from '@mui/material'
import { useEffect, useRef, useState } from 'react'
import BladeIcon from '../../../Icons/BladeIcon/BladeIcon'
import BladeFrame from '../BladeFrame'
import { BladeSelectDefaultProps, BladeSelectProps } from './BladeSelect.props'
import { Ledfx } from '../../../../api/ledfx'
import GifPicker from '../Gif/GifPicker'
import GifFramePicker from '../Gif/GifFramePicker'

/**
 * ## String
 * ### render as `input field` or `select`
 * Renders select if schema.enum is defined properly
 */
const BladeSelect = ({
  variant = 'outlined',
  disabled = false,
  schema,
  model,
  model_id,
  onChange,
  index,
  required = false,
  wrapperStyle = { margin: '0.5rem', flexBasis: '49%', width: 'unset' },
  selectStyle = {},
  textStyle = {},
  menuItemStyle = {},
  hideDesc,
  children,
  type
}: BladeSelectProps) => {
  const inputRef = useRef<any>(null)
  const [icon, setIcon] = useState(
    schema.id === 'icon_name'
      ? (model && model_id && model[model_id]) ||
          (schema.enum && schema.enum[0])
      : ''
  )
  useEffect(() => {
    if (model && model_id && model[model_id] && inputRef.current) {
      inputRef.current.value = model[model_id]
    }
  }, [model, model_id])
  // console.log(schema, model)
  return (
    <BladeFrame
      title={schema.title}
      className={`step-effect-${index}`}
      full={
        !(
          schema.enum &&
          schema.enum.length &&
          Object.values(schema.enum).every((a: any) => a?.length < 20)
        )
      }
      required={required}
      style={{
        ...wrapperStyle,
        flexBasis: schema.title === 'Name' ? '100%' : '49%'
      }}
    >
      {variant === 'contained' ? (
        schema.enum ? (
          <Select
            variant="filled"
            disabled={disabled}
            style={{
              flexGrow: 'unset',
              ...(selectStyle as any)
            }}
            defaultValue={schema.default}
            value={
              (model && model_id && model[model_id]) ||
              schema.default ||
              schema.enum[0]
            }
            onChange={(e) => onChange(model_id, e.target.value)}
          >
            {children ||
              schema.enum.map((item: any, i: number) => (
                <MenuItem key={`${i}-${i}`} value={item}>
                  {item}
                </MenuItem>
              ))}
          </Select>
        ) : (
          <TextField
            helperText={!hideDesc && schema.description}
            defaultValue={
              (model && model_id && model[model_id]) ||
              (schema.enum && schema.enum[0]) ||
              schema.default ||
              ''
            }
            onBlur={(e) => onChange(model_id, e.target.value)}
            style={textStyle as any}
          />
        )
      ) : schema.enum && Array.isArray(schema.enum) ? (
        <Select
          disabled={disabled}
          style={{
            flexGrow: variant === 'outlined' ? 1 : 'unset',
            ...(selectStyle as any)
          }}
          defaultValue={schema.default}
          value={
            (model && model_id && model[model_id]) ||
            schema.default ||
            schema.enum[0]
          }
          onChange={(e) => onChange(model_id, e.target.value)}
        >
          {schema.enum.map((item: any, i: number) => (
            <MenuItem key={i} value={item} style={menuItemStyle as any}>
              {item}
            </MenuItem>
          ))}
        </Select>
      ) : schema.enum && !Array.isArray(schema.enum) ? (
        <Select
          disabled={disabled}
          style={{
            flexGrow: variant === 'outlined' ? 1 : 'unset',
            ...(selectStyle as any)
          }}
          defaultValue={schema.default}
          value={
            (model && model_id && schema.enum[model[model_id]]) ||
            schema.default ||
            schema.enum[0]
          }
          onChange={(e) =>
            onChange(
              model_id,
              parseInt(
                Object.keys(schema.enum).find(
                  (en) => schema.enum[en] === e.target.value
                ) || '0',
                10
              )
            )
          }
        >
          {Object.keys(schema.enum).map((item, i) => (
            <MenuItem key={i} value={schema.enum[item]}>
              {schema.enum[item]}
            </MenuItem>
          ))}
        </Select>
      ) : (
        <>
          <TextField
            inputRef={inputRef}
            type={
              schema.description?.includes('password') ? 'password' : 'unset'
            }
            helperText={!hideDesc && schema.description}
            InputProps={
              schema.id === 'icon_name'
                ? {
                    startAdornment: (
                      <InputAdornment position="start">
                        <BladeIcon name={icon} style={{ color: '#eee' }} />
                      </InputAdornment>
                    )
                  }
                : {}
            }
            defaultValue={
              (model && model_id && model[model_id]) ||
              (schema.enum && schema.enum[0]) ||
              schema.default ||
              ''
            }
            onBlur={(e) => onChange(model_id, e.target.value)}
            onChange={(e) => {
              if (schema.id === 'icon_name') setIcon(e.target.value)
              inputRef.current.value = e.target.value
            }}
            style={textStyle as any}
          />
          {schema.id === 'image_location' && (
            <GifPicker
              onChange={(gif: string) => {
                onChange(model_id, gif)
                inputRef.current.value = gif
              }}
            />
          )}
          {schema.id === 'beat_frames' &&
            model.image_location &&
            model.image_location !== '' && (
              <GifFramePicker
                model={model}
                onChange={(gif: string) => {
                  onChange(model_id, gif)
                  inputRef.current.value = gif
                }}
              />
            )}
          {model_id === 'auth_token' && type === 'nanoleaf' && (
            <Tooltip
              title={
                model.ip_address === undefined || model.ip_address === ''
                  ? 'please enter ip address of nanoleaf controller'
                  : 'please hold power on nanoleaf controller for 7 seconds until white leds scan left to right and then press this button to acquire auth token'
              }
            >
              <Button
                sx={{
                  fontSize: 10,
                  height: 56,
                  color:
                    model.ip_address === undefined || model.ip_address === ''
                      ? 'grey'
                      : 'inherit'
                }}
                onClick={async () => {
                  if (model.ip_address === undefined || model.ip_address === '')
                    return
                  const { auth_token } = await Ledfx(
                    '/api/get_nanoleaf_token',
                    'POST',
                    {
                      ip_address: model.ip_address,
                      port: model.port || 16021
                    }
                  )
                  onChange(model_id, auth_token)
                  inputRef.current.value = auth_token
                }}
              >
                Get Token
              </Button>
            </Tooltip>
          )}
        </>
      )}
    </BladeFrame>
  )
}

BladeSelect.defaultProps = BladeSelectDefaultProps

export default BladeSelect

import { ReactElement, useState } from 'react'
import { styled } from '@mui/material/styles'
import {
  DialogContentText,
  Select,
  MenuItem,
  ListSubheader,
  Switch,
  FormControlLabel,
  Divider
} from '@mui/material'
import { Info } from '@mui/icons-material'
import MicIcon from '@mui/icons-material/Mic'
import SpeakerIcon from '@mui/icons-material/Speaker'
import BladeBoolean from '../components/Boolean/BladeBoolean'
import BladeSelect from '../components/String/BladeSelect'
import BladeSlider from '../components/Number/BladeSlider'
import BladeFrame from '../components/BladeFrame'
import { SchemaFormDefaultProps, SchemaFormProps } from './SchemaForm.props'

const PREFIX = 'SchemaForm'

const classes = {
  bladeSchemaForm: `${PREFIX}-bladeSchemaForm`,
  FormListHeaders: `${PREFIX}-FormListHeaders`,
  bladeSelect: `${PREFIX}-bladeSelect`
}

const Root = styled('div')(({ theme }) => ({
  [`& .${classes.bladeSchemaForm}`]: {
    display: 'flex',
    flexWrap: 'wrap',
    justifyContent: 'space-between'
  },

  [`& .${classes.FormListHeaders}`]: {
    background: theme.palette.secondary.main,
    color: '#fff'
  },

  [`& .${classes.bladeSelect}`]: {
    '& .MuiSelect-select': {
      display: 'flex',
      alignItems: 'center'
    }
  }
}))

/**
 * Dynamically render Forms based on a `schema` <br />
 * most schemas retrived from ledfx/api/schema are read-only <br />
 * to enable write, please provide the key `permitted_keys`
 */
const SchemaForm = ({
  schema,
  model,
  hideToggle,
  onModelChange,
  type
}: SchemaFormProps): ReactElement<any, any> => {
  const [hideDesc, setHideDesc] = useState(true)

  const yzSchema =
    schema &&
    schema.properties &&
    Object.keys(schema.properties)
      .map((sk) => ({
        ...schema.properties[sk],
        id: sk,
        required: schema.required && schema.required.indexOf(sk) !== -1,
        permitted: schema.permitted_keys
          ? schema.permitted_keys.indexOf(sk) > -1
          : true
      }))
      .sort((a, _b) => (a.required ? -1 : 1))
      .sort((a, _b) => (a.id === 'name' ? -1 : 1))

  function onlyUnique(value: string, index: number, self: any) {
    return self.indexOf(value) === index
  }

  return (
    <Root>
      <div className={classes.bladeSchemaForm}>
        {yzSchema &&
          yzSchema.map((s: any, i: number) => {
            switch (s.type) {
              case 'boolean':
                return (
                  <BladeBoolean
                    hideDesc={hideDesc}
                    key={i}
                    index={i}
                    model={model}
                    model_id={s.id}
                    required={s.required}
                    style={{ margin: '0.5rem 0', flexBasis: '49%' }}
                    schema={s}
                    onClick={(model_id: string, value: any) => {
                      const c: Record<string, unknown> = {}
                      c[model_id] = value
                      if (onModelChange) {
                        return onModelChange(c)
                      }
                      return null
                    }}
                  />
                )
              case 'string': {
                const group: any = {}
                let audio_groups: any = []
                if (s.id === 'audio_device') {
                  // eslint-disable-next-line
                for (const [key, value] of Object.entries(schema.properties.audio_device?.enum)) {
                    if (typeof value === 'string') {
                      if (!group[value?.split(':')[0]]) {
                        group[value.split(':')[0]] = {}
                      }
                      // eslint-disable-next-line
                    group[value.split(':')[0]][key] = value.split(':')[1];
                    }
                  }

                  audio_groups = Object.values(
                    schema.properties.audio_device?.enum
                  )
                    .map((d: any) => d.split(':')[0])
                    .filter(onlyUnique)
                }

                return audio_groups?.length ? (
                  <BladeFrame
                    key={i}
                    style={{ order: -1 }}
                    title="Audio Device"
                    full
                  >
                    <Select
                      value={(model && model.audio_device) || 0}
                      fullWidth
                      onChange={(e: any) => {
                        const c: Record<string, unknown> = {}
                        c.audio_device = parseInt(e.target.value, 10)
                        if (onModelChange) {
                          return onModelChange(c)
                        }
                        return null
                      }}
                      className={classes.bladeSelect}
                      id="grouped-select"
                    >
                      {audio_groups?.map((c: string, ind: number) => [
                        <ListSubheader
                          className={classes.FormListHeaders}
                          color="primary"
                          key={ind}
                        >
                          {c}
                        </ListSubheader>,
                        Object.keys(group[c]).map((e) => (
                          <MenuItem
                            value={e}
                            // disabled={group[c][e].indexOf('[Loopback]') > -1}
                          >
                            {group[c][e].indexOf('[Loopback]') > -1 ? (
                              <SpeakerIcon style={{ marginRight: '10px' }} />
                            ) : (
                              <MicIcon style={{ marginRight: '10px' }} />
                            )}
                            {group[c][e].replace('[Loopback]', '')}
                          </MenuItem>
                        ))
                      ])}
                    </Select>
                  </BladeFrame>
                ) : (
                  !(
                    (type === 'mqtt_hass' && s.id === 'name') ||
                    (type === 'mqtt_hass' && s.id === 'description')
                  ) && (
                    <BladeSelect
                      // eslint-disable-next-line
                      children={undefined}
                      hideDesc={hideDesc}
                      type={type}
                      // hide={"test"}
                      model={model}
                      disabled={!s.permitted}
                      wrapperStyle={{
                        margin: '0.5rem 0',
                        width: '49%',
                        flexBasis: 'unset'
                      }}
                      textStyle={{ width: '100%' }}
                      schema={s}
                      required={s.required}
                      model_id={s.id}
                      key={i}
                      index={i}
                      onChange={(model_id: string, value: any) => {
                        const c: Record<string, unknown> = {}
                        c[model_id] = value
                        if (onModelChange) {
                          return onModelChange(c)
                        }
                        return null
                      }}
                    />
                  )
                )
              }
              case 'number':
                return (
                  <BladeSlider
                    step={undefined}
                    hideDesc={hideDesc}
                    disabled={!s.permitted}
                    key={i}
                    model_id={s.id}
                    model={model}
                    required={s.required}
                    schema={s}
                    onChange={(model_id: string, value: any) => {
                      const c: Record<string, unknown> = {}
                      c[model_id] = value
                      if (onModelChange) {
                        return onModelChange(c)
                      }
                      return null
                    }}
                  />
                )

              case 'integer':
                return (
                  <BladeSlider
                    full={s.id === 'delay_ms'}
                    hideDesc={hideDesc}
                    disabled={!s.permitted}
                    step={1}
                    key={i}
                    model_id={s.id}
                    model={model}
                    required={s.required}
                    schema={s}
                    textfield={false}
                    marks={undefined}
                    index={undefined}
                    style={{ margin: '0.5rem 0', width: '49%' }}
                    onChange={(model_id: string, value: any) => {
                      const c: Record<string, unknown> = {}
                      c[model_id] = value
                      if (onModelChange) {
                        return onModelChange(c)
                      }
                      return null
                    }}
                  />
                )
              case 'int':
                return s?.enum?.length > 10 ? (
                  <BladeSlider
                    hideDesc={hideDesc}
                    disabled={!s.permitted}
                    marks={s?.enum}
                    step={undefined}
                    key={i}
                    model_id={s.id}
                    model={model}
                    required={s.required}
                    schema={s}
                    textfield={false}
                    style={{ margin: '0.5rem 0', width: '49%' }}
                    onChange={(model_id: string, value: any) => {
                      const c: Record<string, unknown> = {}
                      c[model_id] = value
                      if (onModelChange) {
                        return onModelChange(c)
                      }
                      return null
                    }}
                  />
                ) : (
                  <BladeSlider
                    hideDesc={hideDesc}
                    disabled={!s.permitted}
                    marks={s?.enum}
                    step={undefined}
                    key={i}
                    model_id={s.id}
                    model={model}
                    required={s.required}
                    schema={s}
                    textfield={false}
                    style={{ margin: '0.5rem 0', width: '49%' }}
                    onChange={(model_id: string, value: any) => {
                      const c: Record<string, unknown> = {}
                      c[model_id] = value
                      if (onModelChange) {
                        return onModelChange(c)
                      }
                      return null
                    }}
                  />
                )
              default:
                return (
                  <>
                    Unsupported type:
                    {s.type}
                  </>
                )
            }
          })}
      </div>
      {!hideToggle && (
        <>
          <Divider style={{ margin: '1rem 0 0.5rem 0' }} />
          <FormControlLabel
            value="start"
            control={
              <Switch
                checked={!hideDesc}
                onChange={(_e) => setHideDesc(!hideDesc)}
              />
            }
            label={
              <DialogContentText
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: 0
                }}
              >
                Field-Descriptions
                <Info style={{ marginLeft: '0.5rem' }} />
              </DialogContentText>
            }
            labelPlacement="end"
          />
        </>
      )}
    </Root>
  )
}

SchemaForm.defaultProps = SchemaFormDefaultProps

export default SchemaForm

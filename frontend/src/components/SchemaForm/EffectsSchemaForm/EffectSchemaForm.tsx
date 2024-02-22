import { styled } from '@mui/material/styles'
import BladeBoolean from '../components/Boolean/BladeBoolean'
import BladeSelect from '../components/String/BladeSelect'
import BladeSlider from '../components/Number/BladeSlider'
import GradientPickerWrapper from '../components/GradientPicker/GradientPicker.wrapper'
import {
  EffectSchemaFormDefaultProps,
  EffectSchemaFormProps
} from './EffectSchemaForm.props'

const PREFIX = 'EffectSchemaForm'

const classes = {
  bladeSchemaForm: `${PREFIX}-bladeSchemaForm`
}

const Root = styled('div')({
  [`&.${classes.bladeSchemaForm}`]: {
    display: 'flex',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    '& *': {
      boxSizing: 'border-box'
    }
  }
})

const EffectSchemaForm = ({
  schemaProperties,
  model,
  virtId,
  handleEffectConfig,
  descriptions
}: EffectSchemaFormProps) => {
  return (
    <Root className={classes.bladeSchemaForm}>
      {schemaProperties &&
        model &&
        schemaProperties.map((s: any, i: number) => {
          switch (s.type) {
            case 'boolean':
              return (
                <BladeBoolean
                  key={i}
                  index={i}
                  model={model}
                  model_id={s.id}
                  schema={s}
                  hideDesc={descriptions !== 'Show'}
                  onClick={(model_id: string, value: any) => {
                    const c: Record<string, unknown> = {}
                    c[model_id] = value
                    return handleEffectConfig && handleEffectConfig(c)
                  }}
                />
              )
            case 'string':
              return (
                <BladeSelect
                  model={model}
                  schema={s}
                  wrapperStyle={{ width: '49%' }}
                  model_id={s.id}
                  key={i}
                  index={i}
                  hideDesc={descriptions === 'Hide'}
                  onChange={(model_id: string, value: any) => {
                    const c: Record<string, unknown> = {}
                    c[model_id] = value
                    return handleEffectConfig && handleEffectConfig(c)
                  }}
                />
              )

            case 'number':
              return (
                <BladeSlider
                  key={i}
                  index={i}
                  hideDesc={descriptions !== 'Show'}
                  model_id={s.id}
                  model={model}
                  schema={s}
                  onChange={(model_id: string, value: any) => {
                    const c: Record<string, unknown> = {}
                    c[model_id] = value
                    return handleEffectConfig && handleEffectConfig(c)
                  }}
                />
              )

            case 'integer':
              return (
                <BladeSlider
                  step={1}
                  key={i}
                  index={i}
                  hideDesc={descriptions !== 'Show'}
                  model_id={s.id}
                  model={model}
                  schema={s}
                  style={{ margin: '0.5rem 0' }}
                  onChange={(model_id: string, value: any) => {
                    const c: Record<string, unknown> = {}
                    c[model_id] = value
                    return handleEffectConfig && handleEffectConfig(c)
                  }}
                />
              )
            case 'color':
              return (
                <GradientPickerWrapper
                  pickerBgColor={model[s.id]}
                  key={i}
                  index={i}
                  title={s.id}
                  hideDesc={descriptions === 'Hide'}
                  // selectedType={selectedType}
                  // model={model}
                  virtId={virtId}
                  wrapperStyle={{ width: '49%' }}
                  isGradient={s.gradient}
                />
              )
            default:
              return (
                <>
                  Unsupported type:--
                  {s.type}
                </>
              )
          }
        })}
    </Root>
  )
}

EffectSchemaForm.defaultProps = EffectSchemaFormDefaultProps

export default EffectSchemaForm

export interface BladeSliderInnerProps {
  schema?: any
  model?: any
  model_id?: string
  step?: number
  onChange?: any
  textfield?: boolean
  style?: any
  disabled?: boolean
  marks?: any
  hideDesc?: boolean
  disableUnderline?: boolean
  full?: boolean
}

export const BladeSliderInnerDefaultProps = {
  schema: undefined,
  model: undefined,
  model_id: '',
  step: undefined,
  onChange: undefined,
  textfield: undefined,
  style: undefined,
  disabled: undefined,
  marks: undefined,
  hideDesc: undefined,
  full: undefined
}

export interface BladeSliderProps {
  /**
   * `outlined` or not. More might come
   */
  variant?: string
  /**
   * Renders slider if:
   *
   *  - schema.maximum && !textfield
   *  - schema.enum && !textfield
   *
   * Else: renders input field
   */
  schema?: any
  /**
   * current value representation of schema
   */
  model?: any
  model_id?: string
  /**
   * if steps not provided it will be calculated like:
   * `schema.maximum > 1 ? 0.1 : 0.01`
   */
  step?: number
  onChange?: any
  marks?: any
  index?: number
  required?: boolean
  /**
   * Forces input field rendering.
   * no slider
   */
  textfield?: boolean
  disabled?: boolean
  hideDesc?: boolean
  style?: any
  full?: boolean
}

export const BladeSliderDefaultProps = {
  variant: 'outlined',
  disableUnderline: undefined,
  schema: {
    title: 'Slide me'
  },
  model: undefined,
  model_id: '',
  step: undefined,
  onChange: undefined,
  marks: undefined,
  index: undefined,
  required: false,
  textfield: false,
  disabled: false,
  hideDesc: false,
  style: {},
  full: false
}

export interface BladeBooleanProps {
  index?: number
  required?: boolean
  style?: any
  onClick?: any
  type?: 'switch' | 'checkbox' | 'button'
  schema?: any
  model?: Record<string, unknown>
  hideDesc?: boolean
  model_id: string
}

export const BladeBooleanDefaultProps = {
  index: undefined,
  style: undefined,
  required: false,
  onClick: undefined,
  type: 'switch',
  schema: {
    title: 'Check me'
  },
  model: undefined,
  hideDesc: undefined,
  model_id: undefined
}

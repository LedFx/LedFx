export interface Schema {
  properties?: any
  required?: any
  permitted_keys?: any
}

export interface SchemaFormProps {
  /**
   * Schema to generate Form from. <br />
   * in production this is provided by <br />
   * an external api or a store-management. <br />
   * See examples, for manual usage...
   */
  schema: Schema
  /**
   * Model is the current value of the schema
   */
  model: Record<string, unknown>
  /**
   * Hide Field-Description Toggle
   */
  hideToggle?: boolean
  /**
   * onChange function for the given model
   */
  onModelChange?: (e: any) => typeof e
  /**
   * internal
   */
  type?: string
}

export const SchemaFormDefaultProps = {
  hideToggle: undefined,
  onModelChange: undefined,
  type: undefined
}

import { Switch, Checkbox, Button, Typography } from '@mui/material'
import BladeFrame from '../BladeFrame'
import {
  BladeBooleanDefaultProps,
  BladeBooleanProps
} from './BladeBoolean.props'

/**
 * ## Boolean
 * ### render as `switch`,`checkbox` or `button`
 */
const BladeBoolean = ({
  onClick,
  index,
  required,
  style,
  type,
  schema,
  model,
  hideDesc = false,
  model_id
}: BladeBooleanProps) => {
  switch (type) {
    case 'switch':
      return (
        <BladeFrame
          index={index}
          required={required}
          style={style}
          title={schema.title.replaceAll('_', ' ').replaceAll('Color', 'c')}
        >
          <Switch
            defaultValue={(model && model[model_id]) || schema.default}
            checked={model && !!model[model_id]}
            onChange={(e, b) => onClick(model_id, b)}
            name={schema.title.replaceAll('_', ' ').replaceAll('color', 'c')}
            color="primary"
          />
          {!hideDesc && schema.description ? (
            <Typography variant="body2" className="MuiFormHelperText-root">
              {schema.description}{' '}
            </Typography>
          ) : null}
        </BladeFrame>
      )
    case 'checkbox':
      return (
        <BladeFrame
          index={index}
          title={schema.title.replaceAll('_', ' ').replaceAll('Color', 'c')}
        >
          <Checkbox
            defaultValue={schema.default}
            checked={model && !!model[model_id]}
            onChange={(e, b) => onClick(model_id, b)}
            name={model_id}
            color="primary"
          />
        </BladeFrame>
      )
    case 'button':
      return (
        <Button
          color="primary"
          variant={model && model[model_id] ? 'contained' : 'outlined'}
          onClick={() => onClick(model_id, model && !model[model_id])}
        >
          {schema.title.replaceAll('_', ' ').replaceAll('color', 'c')}
        </Button>
      )

    default:
      return <div>unset</div>
  }
}

BladeBoolean.defaultProps = BladeBooleanDefaultProps

export default BladeBoolean

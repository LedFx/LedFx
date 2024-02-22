import { Card, CardContent } from '@mui/material'
import { ComponentStory, ComponentMeta } from '@storybook/react'
// eslint-disable-next-line
import EffectSchemaForm from './EffectSchemaForm';

export default {
  /* 👇 The title prop is optional.
   * See https://storybook.js.org/docs/react/configure/overview#configure-story-loading
   * to learn how to generate automatic titles
   */
  title: 'UI Components/SchemaForm/Examples',
  component: EffectSchemaForm,
  argTypes: {
    type: {
      control: false
    }
  },
  decorators: [
    (Story) => (
      <Card style={{ maxWidth: 800 }}>
        <CardContent>{Story()}</CardContent>
      </Card>
    )
  ],
  parameters: {
    options: {
      showPanel: true,
      panelPosition: 'bottom'
    }
  }
} as ComponentMeta<typeof EffectSchemaForm>

// eslint-disable-next-line
const Template: ComponentStory<typeof EffectSchemaForm> = (args) => (
  <EffectSchemaForm {...args} />
)

export const EffectForm = Template.bind({})
EffectForm.storyName = 'Effect Schema'
EffectForm.args = {
  schemaProperties: [
    {
      id: 'flip',
      type: 'boolean',
      title: 'Flip',
      description: 'Flip the effect',
      default: false
    },
    {
      id: 'brightness',
      type: 'number',
      minimum: 0,
      maximum: 1,
      title: 'Brightness',
      description: 'Brightness of strip',
      default: 1
    },
    {
      id: 'background_brightness',
      type: 'number',
      minimum: 0,
      maximum: 1,
      title: 'Background Brightness',
      description: 'Brightness of the background color',
      default: 1
    },
    {
      id: 'gradient',
      type: 'color',
      gradient: true,
      title: 'Gradient',
      description: 'Color gradient to display',
      default:
        'linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 120, 0) 14%, rgb(255, 200, 0) 28%, rgb(0, 255, 0) 42%, rgb(0, 199, 140) 56%, rgb(0, 0, 255) 70%, rgb(128, 0, 128) 84%, rgb(255, 0, 178) 98%)'
    },
    {
      id: 'gradient_roll',
      type: 'number',
      minimum: 0,
      maximum: 10,
      title: 'Gradient Roll',
      description: 'Amount to shift the gradient',
      default: 0
    },
    {
      id: 'mirror',
      type: 'boolean',
      title: 'Mirror',
      description: 'Mirror the effect',
      default: false
    },
    {
      id: 'blur',
      type: 'number',
      minimum: 0,
      maximum: 10,
      title: 'Blur',
      description: 'Amount to blur the effect',
      default: 2
    },
    {
      id: 'decay',
      type: 'number',
      minimum: 0,
      maximum: 1,
      title: 'Decay',
      description: 'Rate of color decay',
      default: 0.7
    },
    {
      id: 'multiplier',
      type: 'number',
      minimum: 0,
      maximum: 1,
      title: 'Multiplier',
      description: 'Make the reactive bar bigger/smaller',
      default: 0.5
    },
    {
      id: 'background_color',
      type: 'color',
      gradient: false,
      title: 'Background Color',
      description: 'Color of Background',
      default: '#000000'
    },
    {
      id: 'frequency_range',
      type: 'string',
      enum: ['Beat', 'Bass', 'Lows (beat+bass)', 'Mids', 'High'],
      title: 'Frequency Range',
      description: 'Frequency range for the beat detection',
      default: 'Lows (beat+bass)'
    },
    {
      id: 'invert_roll',
      type: 'boolean',
      title: 'Invert Roll',
      description: 'Invert the direction of the gradient roll',
      default: false
    }
  ],
  model: {
    blur: 2,
    decay: 0.7,
    frequency_range: 'Lows (beat+bass)',
    brightness: 1,
    mirror: false,
    invert_roll: false,
    multiplier: 0.5,
    gradient: 'linear-gradient(90deg, #00ffff 0.00%,#0000ff 100.00%)',
    gradient_roll: 0,
    background_color: '#000080',
    background_brightness: 1,
    flip: false
  },
  handleEffectConfig: (e: any) => {
    // eslint-disable-next-line no-console
    console.log('Update Effect', e)
    return true
  }
}

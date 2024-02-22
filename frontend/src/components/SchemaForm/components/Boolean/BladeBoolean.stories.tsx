import { Card, CardContent } from '@mui/material'
import { ComponentStory, ComponentMeta } from '@storybook/react'
// eslint-disable-next-line
import BladeBoolean from "./BladeBoolean";

export default {
  title: 'UI Components/SchemaForm/Components',
  component: BladeBoolean,
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
} as ComponentMeta<typeof BladeBoolean>

// eslint-disable-next-line
const Template: ComponentStory<typeof BladeBoolean> = (args) => <BladeBoolean {...args} />;

export const Boolean = Template.bind({})
Boolean.args = {
  type: 'switch',
  required: false,
  hideDesc: undefined,
  index: 1,
  style: undefined,
  onClick: undefined,
  schema: {
    title: 'Check me',
    description: 'some nice description'
  },
  model: undefined,
  model_id: undefined
}

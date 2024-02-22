import { Card, CardContent } from '@mui/material'
import { ComponentStory, ComponentMeta } from '@storybook/react'
// eslint-disable-next-line
import BladeSchemaForm from "./SchemaForm";

export default {
  /* 👇 The title prop is optional.
   * See https://storybook.js.org/docs/react/configure/overview#configure-story-loading
   * to learn how to generate automatic titles
   */
  title: 'UI Components/SchemaForm',
  component: BladeSchemaForm,
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
} as ComponentMeta<typeof BladeSchemaForm>

// eslint-disable-next-line
const Template: ComponentStory<typeof BladeSchemaForm> = (args) => <BladeSchemaForm {...args} />;

export const Default = Template.bind({})
Default.storyName = 'Default'
Default.args = {
  schema: {
    properties: {},
    permitted_keys: [],
    required: []
  },
  model: {},
  // eslint-disable-next-line
  onModelChange: (e) => console.log(e),
  hideToggle: false
}

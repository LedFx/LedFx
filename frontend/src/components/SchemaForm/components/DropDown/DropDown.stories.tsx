import { Card, CardContent } from '@mui/material'
import { ComponentStory, ComponentMeta } from '@storybook/react'
// eslint-disable-next-line
import DropDown from "./DropDown";

export default {
  /* 👇 The title prop is optional.
   * See https://storybook.js.org/docs/react/configure/overview#configure-story-loading
   * to learn how to generate automatic titles
   */
  title: 'UI Components/SchemaForm/Components',
  component: DropDown,
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
} as ComponentMeta<typeof DropDown>

// eslint-disable-next-line
const Template: ComponentStory<typeof DropDown> = (args) => <DropDown {...args} />;

export const GroupedDropdown = Template.bind({})
GroupedDropdown.storyName = 'Grouped Dropdown'
GroupedDropdown.args = {
  title: 'Grouped Dropdown',
  showFilter: false,
  groups: {
    'Group 1': [
      {
        name: 'Item 1',
        id: 'item11',
        category: 'Group 1'
      },
      {
        name: 'Item2',
        id: 'item12',
        category: 'Group 1'
      }
    ],
    'Group 2': [
      {
        name: 'Item 1',
        id: 'item21',
        category: 'Group 2'
      }
    ]
  },
  value: 'item11',
  onChange: undefined
}

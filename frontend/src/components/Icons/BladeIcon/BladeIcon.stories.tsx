import { ComponentStory, ComponentMeta } from '@storybook/react'
// eslint-disable-next-line
import BladeIcon from './BladeIcon';

export default {
  /* 👇 The title prop is optional.
   * See https://storybook.js.org/docs/react/configure/overview#configure-story-loading
   * to learn how to generate automatic titles
   */
  title: 'UI Components/Icon',
  component: BladeIcon,
  parameters: {
    options: {
      showPanel: true
    }
  }
} as ComponentMeta<typeof BladeIcon>

// eslint-disable-next-line
const Template: ComponentStory<typeof BladeIcon> = (args) => <BladeIcon {...args} />;

export const Default = Template.bind({})
Default.args = {}

export const WLED = Template.bind({})
WLED.args = {
  name: 'wled'
}

export const MUI = Template.bind({})
MUI.args = {
  name: 'Light'
}

export const MDI = Template.bind({})
MDI.args = {
  name: 'mdi:led-strip'
}

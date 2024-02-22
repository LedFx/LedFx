import { Card, CardContent } from '@mui/material'
import { ComponentStory, ComponentMeta } from '@storybook/react'

// eslint-disable-next-line
import GradientPicker from "./GradientPicker";

export default {
  title: 'UI Components/SchemaForm/Components',
  component: GradientPicker,
  argTypes: {
    sendColorToVirtuals: { action: 'clicked' },
    pickerBgColor: {
      table: {
        disable: true
      }
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
      panelPosition: 'right'
    }
  }
} as ComponentMeta<typeof GradientPicker>

// eslint-disable-next-line
const Template: ComponentStory<typeof GradientPicker> = (args) => <GradientPicker {...args} />;

export const Color = Template.bind({})
Color.args = {
  pickerBgColor: '#800000',
  title: 'Color',
  index: 1,
  isGradient: false,
  wrapperStyle: undefined,
  colors: {
    colors: {
      builtin: {
        red: '#ff0000',
        'orange-deep': '#ff2800',
        orange: '#ff7800',
        yellow: '#ffc800',
        'yellow-acid': '#a0ff00',
        green: '#00ff00',
        'green-forest': '#228b22',
        'green-spring': '#00ff7f',
        'green-teal': '#008080',
        'green-turquoise': '#00c78c',
        'green-coral': '#00ff32',
        cyan: '#00ffff',
        blue: '#0000ff',
        'blue-light': '#4169e1',
        'blue-navy': '#000080',
        'blue-aqua': '#00ffff',
        purple: '#800080',
        pink: '#ff00b2',
        magenta: '#ff00ff',
        black: '#000000',
        white: '#ffffff',
        gold: '#ffd700',
        hotpink: '#ff69b4',
        lightblue: '#add8e6',
        lightgreen: '#98fb98',
        lightpink: '#ffb6c1',
        lightyellow: '#ffffe0',
        maroon: '#800000',
        mint: '#bdfcc9',
        olive: '#556b2f',
        peach: '#ff6464',
        plum: '#dda0dd',
        sepia: '#5e2612',
        skyblue: '#87ceeb',
        steelblue: '#4682b4',
        tan: '#d2b48c',
        violetred: '#d02090'
      },
      user: {}
    },
    gradients: {
      builtin: {
        Rainbow:
          'linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 120, 0) 14%, rgb(255, 200, 0) 28%, rgb(0, 255, 0) 42%, rgb(0, 199, 140) 56%, rgb(0, 0, 255) 70%, rgb(128, 0, 128) 84%, rgb(255, 0, 178) 98%)',
        Dancefloor:
          'linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 0, 178) 50%, rgb(0, 0, 255) 100%)',
        Plasma:
          'linear-gradient(90deg, rgb(0, 0, 255) 0%, rgb(128, 0, 128) 25%, rgb(255, 0, 0) 50%, rgb(255, 40, 0) 75%, rgb(255, 200, 0) 100%)',
        Ocean:
          'linear-gradient(90deg, rgb(0, 255, 255) 0%, rgb(0, 0, 255) 100%)',
        Viridis:
          'linear-gradient(90deg, rgb(128, 0, 128) 0%, rgb(0, 0, 255) 25%, rgb(0, 128, 128) 50%, rgb(0, 255, 0) 75%, rgb(255, 200, 0) 100%)',
        Jungle:
          'linear-gradient(90deg, rgb(0, 255, 0) 0%, rgb(34, 139, 34) 50%, rgb(255, 120, 0) 100%)',
        Spring:
          'linear-gradient(90deg, rgb(255, 0, 178) 0%, rgb(255, 40, 0) 50%, rgb(255, 200, 0) 100%)',
        Winter:
          'linear-gradient(90deg, rgb(0, 199, 140) 0%, rgb(0, 255, 50) 100%)',
        Frost:
          'linear-gradient(90deg, rgb(0, 0, 255) 0%, rgb(0, 255, 255) 33%, rgb(128, 0, 128) 66%, rgb(255, 0, 178) 99%)',
        Sunset:
          'linear-gradient(90deg, rgb(0, 0, 128) 0%, rgb(255, 120, 0) 50%, rgb(255, 0, 0) 100%)',
        Borealis:
          'linear-gradient(90deg, rgb(255, 40, 0) 0%, rgb(128, 0, 128) 33%, rgb(0, 199, 140) 66%, rgb(0, 255, 0) 99%)',
        Rust: 'linear-gradient(90deg, rgb(255, 40, 0) 0%, rgb(255, 0, 0) 100%)',
        Winamp:
          'linear-gradient(90deg, rgb(0, 255, 0) 0%, rgb(255, 200, 0) 25%, rgb(255, 120, 0) 50%, rgb(255, 40, 0) 75%, rgb(255, 0, 0) 100%)'
      },
      user: {
        '1': 'linear-gradient(90deg, #00ffff 0.00%,#0000ff 100.00%)',
        '2': 'linear-gradient(90deg, #00ffff 0.00%,#0000ff 100.00%)'
      }
    }
  },
  handleAddGradient: undefined
}

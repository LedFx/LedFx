import { Card, CardContent } from '@mui/material'
import { ComponentStory, ComponentMeta } from '@storybook/react'
// eslint-disable-next-line
import DropDown from "./DropDown";

export default {
  /* 👇 The title prop is optional.
   * See https://storybook.js.org/docs/react/configure/overview#configure-story-loading
   * to learn how to generate automatic titles
   */
  title: 'UI Components/SchemaForm/Examples',
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

export const EffectType = Template.bind({})
EffectType.storyName = 'Effect Type'
EffectType.args = {
  showFilter: false,
  groups: {
    'Non-Reactive': [
      {
        name: 'Gradient',
        id: 'gradient',
        category: 'Non-Reactive'
      },
      {
        name: 'Fade',
        id: 'fade',
        category: 'Non-Reactive'
      },
      {
        name: 'Rainbow',
        id: 'rainbow',
        category: 'Non-Reactive'
      },
      {
        name: 'Single Color',
        id: 'singleColor',
        category: 'Non-Reactive'
      }
    ],
    '2D': [
      {
        name: 'Bands',
        id: 'bands',
        category: '2D'
      },
      {
        name: 'Bands Matrix',
        id: 'bands_matrix',
        category: '2D'
      },
      {
        name: 'Blocks',
        id: 'blocks',
        category: '2D'
      },
      {
        name: 'Equalizer',
        id: 'equalizer',
        category: '2D'
      }
    ],
    BPM: [
      {
        name: 'Bar',
        id: 'bar',
        category: 'BPM'
      },
      {
        name: 'Multicolor Bar',
        id: 'multiBar',
        category: 'BPM'
      },
      {
        name: 'BPM Strobe',
        id: 'strobe',
        category: 'BPM'
      }
    ],
    Classic: [
      {
        name: 'Blade Power+',
        id: 'blade_power_plus',
        category: 'Classic'
      },
      {
        name: 'Energy',
        id: 'energy',
        category: 'Classic'
      },
      {
        name: 'Magnitude',
        id: 'magnitude',
        category: 'Classic'
      },
      {
        name: 'Pitch Spectrum',
        id: 'pitchSpectrum',
        category: 'Classic'
      },
      {
        name: 'Power',
        id: 'power',
        category: 'Classic'
      },
      {
        name: 'Rain',
        id: 'rain',
        category: 'Classic'
      },
      {
        name: 'Strobe',
        id: 'real_strobe',
        category: 'Classic'
      },
      {
        name: 'Scroll',
        id: 'scroll',
        category: 'Classic'
      },
      {
        name: 'Spectrum',
        id: 'spectrum',
        category: 'Classic'
      },
      {
        name: 'Wavelength',
        id: 'wavelength',
        category: 'Classic'
      }
    ],
    Atmospheric: [
      {
        name: 'Block Reflections',
        id: 'block_reflections',
        category: 'Atmospheric'
      },
      {
        name: 'Crawler',
        id: 'crawler',
        category: 'Atmospheric'
      },
      {
        name: 'Energy 2',
        id: 'energy2',
        category: 'Atmospheric'
      },
      {
        name: 'Fire',
        id: 'fire',
        category: 'Atmospheric'
      },
      {
        name: 'Glitch',
        id: 'glitch',
        category: 'Atmospheric'
      },
      {
        name: 'Lava lamp',
        id: 'lava_lamp',
        category: 'Atmospheric'
      },
      {
        name: 'Marching',
        id: 'marching',
        category: 'Atmospheric'
      },
      {
        name: 'Melt',
        id: 'melt',
        category: 'Atmospheric'
      }
    ]
  },
  value: '',
  onChange: undefined
}

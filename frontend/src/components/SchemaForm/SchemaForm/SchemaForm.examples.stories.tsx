import { Card, CardContent } from '@mui/material'
import { ComponentStory, ComponentMeta } from '@storybook/react'
// eslint-disable-next-line
import BladeSchemaForm from "./SchemaForm";

export default {
  /* 👇 The title prop is optional.
   * See https://storybook.js.org/docs/react/configure/overview#configure-story-loading
   * to learn how to generate automatic titles
   */
  title: 'UI Components/SchemaForm/Examples',
  component: BladeSchemaForm,
  argTypes: {
    type: {
      control: false
    }
  },
  parameters: {
    options: {
      showPanel: true,
      panelPosition: 'bottom'
    }
  },
  decorators: [
    (Story) => (
      <Card style={{ maxWidth: 800 }}>
        <CardContent>{Story()}</CardContent>
      </Card>
    )
  ]
} as ComponentMeta<typeof BladeSchemaForm>

// eslint-disable-next-line
const Template: ComponentStory<typeof BladeSchemaForm> = (args) => <BladeSchemaForm {...args} />;

export const AddDeviceAdaLight = Template.bind({})
AddDeviceAdaLight.args = {
  schema: {
    properties: {
      name: {
        type: 'string',
        title: 'Name',
        description: 'Friendly name for the device'
      },
      icon_name: {
        type: 'string',
        title: 'Icon Name',
        description: 'https://material-ui.com/components/material-icons/',
        default: 'mdi:led-strip'
      },
      center_offset: {
        type: 'integer',
        title: 'Center Offset',
        description: 'Number of pixels from the perceived center of the device',
        default: 0
      },
      refresh_rate: {
        type: 'int',
        enum: [10, 12, 16, 21, 32, 64],
        title: 'Refresh Rate',
        description: 'Target rate that pixels are sent to the device',
        default: 64
      },
      com_port: {
        type: 'string',
        enum: ['COM1'],
        title: 'Com Port',
        description: 'COM port for Adalight compatible device'
      },
      baudrate: {
        type: 'integer',
        minimum: 115200,
        title: 'Baudrate',
        description: 'baudrate',
        default: 500000
      },
      pixel_count: {
        type: 'integer',
        minimum: 1,
        title: 'Pixel Count',
        description: 'Number of individual pixels',
        default: 1
      },
      color_order: {
        type: 'string',
        enum: ['RGB', 'RBG', 'GRB', 'BRG', 'GBR', 'BGR'],
        title: 'Color Order',
        description: 'Color order',
        default: 'RGB'
      }
    },
    permitted_keys: [
      'name',
      'icon_name',
      'center_offset',
      'refresh_rate',
      'com_port',
      'baudrate',
      'pixel_count',
      'color_order'
    ],
    required: ['name', 'com_port', 'baudrate', 'pixel_count', 'color_order']
  },
  model: {},
  // eslint-disable-next-line
  onModelChange: (e) => console.log(e),
  hideToggle: false
}

export const AddDeviceWLED = Template.bind({})
AddDeviceWLED.args = {
  schema: {
    properties: {
      name: {
        type: 'string',
        title: 'Name',
        description: 'Friendly name for the device'
      },
      icon_name: {
        type: 'string',
        title: 'Icon Name',
        description: 'https://material-ui.com/components/material-icons/',
        default: 'mdi:led-strip'
      },
      center_offset: {
        type: 'integer',
        title: 'Center Offset',
        description: 'Number of pixels from the perceived center of the device',
        default: 0
      },
      refresh_rate: {
        type: 'int',
        enum: [10, 12, 16, 21, 32, 64],
        title: 'Refresh Rate',
        description: 'Target rate that pixels are sent to the device',
        default: 64
      },
      ip_address: {
        type: 'string',
        title: 'Ip Address',
        description: 'Hostname or IP address of the device'
      },
      sync_mode: {
        type: 'string',
        enum: ['UDP', 'DDP', 'E131'],
        title: 'Sync Mode',
        description:
          'Streaming protocol to WLED device. Recommended: UDP<480px, DDP>480px',
        default: 'UDP'
      },
      timeout: {
        type: 'integer',
        minimum: 0,
        maximum: 255,
        title: 'Timeout',
        description: 'Time between LedFx effect off and WLED effect activate',
        default: 1
      }
    },
    permitted_keys: [
      'name',
      'icon_name',
      'center_offset',
      'refresh_rate',
      'ip_address',
      'sync_mode',
      'timeout'
    ],
    required: ['name', 'ip_address']
  },
  model: {},
  // eslint-disable-next-line
  onModelChange: (e) => console.log(e),
  hideToggle: false
}

export const AddDeviceUDP = Template.bind({})
AddDeviceUDP.args = {
  schema: {
    properties: {
      name: {
        type: 'string',
        title: 'Name',
        description: 'Friendly name for the device'
      },
      icon_name: {
        type: 'string',
        title: 'Icon Name',
        description: 'https://material-ui.com/components/material-icons/',
        default: 'mdi:led-strip'
      },
      center_offset: {
        type: 'integer',
        title: 'Center Offset',
        description: 'Number of pixels from the perceived center of the device',
        default: 0
      },
      refresh_rate: {
        type: 'int',
        enum: [10, 12, 16, 21, 32, 64],
        title: 'Refresh Rate',
        description: 'Target rate that pixels are sent to the device',
        default: 64
      },
      ip_address: {
        type: 'string',
        title: 'Ip Address',
        description: 'Hostname or IP address of the device'
      },
      pixel_count: {
        type: 'integer',
        minimum: 1,
        title: 'Pixel Count',
        description: 'Number of individual pixels',
        default: 1
      },
      port: {
        type: 'integer',
        minimum: 1,
        maximum: 65535,
        title: 'Port',
        description: 'Port for the UDP device',
        default: 21324
      },
      udp_packet_type: {
        type: 'string',
        enum: ['DRGB', 'WARLS', 'DRGBW', 'DNRGB', 'adaptive_smallest'],
        title: 'Udp Packet Type',
        description: 'RGB packet encoding',
        default: 'DRGB'
      },
      timeout: {
        type: 'integer',
        minimum: 1,
        maximum: 255,
        title: 'Timeout',
        description:
          'Seconds to wait after the last received packet to yield device control',
        default: 1
      },
      minimise_traffic: {
        type: 'boolean',
        title: 'Minimise Traffic',
        description:
          'Will not send updates if nothing has changed on the LED device',
        default: true
      }
    },
    permitted_keys: [
      'name',
      'icon_name',
      'center_offset',
      'refresh_rate',
      'ip_address',
      'pixel_count',
      'port',
      'udp_packet_type',
      'timeout',
      'minimise_traffic'
    ],
    required: ['name', 'ip_address', 'pixel_count', 'port', 'udp_packet_type']
  },
  model: {},
  // eslint-disable-next-line
  onModelChange: (e) => console.log(e),
  hideToggle: false
}

export const AddVirtual = Template.bind({})
AddVirtual.args = {
  schema: {
    properties: {
      name: {
        type: 'string',
        title: 'Name',
        description: 'Friendly name for the device'
      },
      mapping: {
        type: 'string',
        enum: ['span', 'copy'],
        title: 'Mapping',
        description:
          'Span: Effect spans all segments. Copy: Effect copied on each segment',
        default: 'span'
      },
      icon_name: {
        type: 'string',
        title: 'Icon Name',
        description: 'Icon for the device*',
        default: 'mdi:led-strip-variant'
      },
      max_brightness: {
        type: 'number',
        minimum: 0,
        maximum: 1,
        title: 'Max Brightness',
        description: 'Max brightness for the device',
        default: 1
      },
      center_offset: {
        type: 'integer',
        title: 'Center Offset',
        description: 'Number of pixels from the perceived center of the device',
        default: 0
      },
      preview_only: {
        type: 'boolean',
        title: 'Preview Only',
        description: 'Preview the pixels without updating the devices',
        default: false
      },
      transition_time: {
        type: 'number',
        minimum: 0,
        maximum: 5,
        title: 'Transition Time',
        description: 'Length of transition between effects',
        default: 0.4
      },
      transition_mode: {
        type: 'string',
        enum: [
          'Add',
          'Dissolve',
          'Push',
          'Slide',
          'Iris',
          'Through White',
          'Through Black',
          'None'
        ],
        title: 'Transition Mode',
        description: 'Type of transition between effects',
        default: 'Add'
      },
      frequency_min: {
        type: 'integer',
        minimum: 20,
        maximum: 15000,
        title: 'Frequency Min',
        description: 'Lowest frequency audio reactive effects of this virtual',
        default: 20
      },
      frequency_max: {
        type: 'integer',
        minimum: 20,
        maximum: 15000,
        title: 'Frequency Max',
        description: 'Highest frequency audio reactive effects of this virtual',
        default: 15000
      }
    },
    permitted_keys: [
      'name',
      'mapping',
      'icon_name',
      'max_brightness',
      'center_offset',
      'preview_only',
      'transition_time',
      'transition_mode',
      'frequency_min',
      'frequency_max'
    ],
    required: ['name', 'mapping']
  },
  model: {},
  // eslint-disable-next-line
  onModelChange: (e) => console.log(e),
  hideToggle: false
}

export const AudioCard = Template.bind({})
AudioCard.args = {
  schema: {
    properties: {
      sample_rate: {
        type: 'integer',
        title: 'Sample Rate',
        default: 60
      },
      mic_rate: {
        type: 'integer',
        title: 'Mic Rate',
        default: 30000
      },
      fft_size: {
        type: 'integer',
        title: 'Fft Size',
        default: 4096
      },
      min_volume: {
        type: 'number',
        minimum: 0,
        maximum: 10,
        title: 'Min Volume',
        default: 0.2
      },
      audio_device: {
        type: 'string',
        enum: {
          0: 'MME: Microsoft Soundmapper - Input',
          1: 'MME: USB Headphones (USB PnP Audio D',
          2: 'MME: VoiceMeeter Output (VB-Audio Vo',
          3: 'MME: Mikrofon (Virtual Desktop Audio',
          10: 'Windows DirectSound: Primärer Soundaufnahmetreiber',
          11: 'Windows DirectSound: USB Headphones (USB PnP Audio Device)',
          12: 'Windows DirectSound: VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)',
          13: 'Windows DirectSound: Mikrofon (Virtual Desktop Audio)',
          26: 'Windows WASAPI: USB Headphones (USB PnP Audio Device)',
          27: 'Windows WASAPI: VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)',
          28: 'Windows WASAPI: Mikrofon (Virtual Desktop Audio)',
          30: 'Windows WDM-KS: Mikrofon (VDVAD Wave)',
          32: 'Windows WDM-KS: Eingang (Realtek HD Audio Line input)',
          33: 'Windows WDM-KS: Mikrofon (Realtek HD Audio Mic input)',
          35: 'Windows WDM-KS: Stereomix (Realtek HD Audio Stereo input)',
          37: 'Windows WDM-KS: Mikrofon (USB PnP Audio Device)',
          40: 'Windows WDM-KS: VoiceMeeter Output (VoiceMeeter vaio)',
          43: 'Windows WDM-KS: Kopfhörer (@System32\\drivers\\bthhfenum.sys,#2;%1 Hands-Free%0\r\n;(Jabra Elite 75t))'
        },
        title: 'Audio Device',
        default: 1
      }
    },
    permitted_keys: ['min_volume', 'audio_device'],
    required: []
  },
  model: {},
  // eslint-disable-next-line
  onModelChange: (e) => console.log(e),
  hideToggle: false
}

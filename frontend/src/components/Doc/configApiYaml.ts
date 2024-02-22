export const configApiYaml = `
openapi: 3.1.0
info:
  title: LedFx API
  version: '1.0'
  summary: LedFx API
  description: LedFx API
  contact: {}
  license:
    name: GPL3
    identifier: GPL-3.0-or-later
servers:
  - url: 'http://localhost:8080/api'
    description: Core
paths:
  /config:
    get:
      summary: GET config
      tags: []
      operationId: get-config
      parameters: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                description: ''
                type: object
                x-examples:
                  example-1:
                    config: 'C:\\Users\\Blade'
                    devices:
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.177
                          name: Couch
                          pixel_count: 36
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: Couch
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.178
                          name: Kitchen
                          pixel_count: 51
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: Kitchen
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.176
                          name: TV-WZ
                          pixel_count: 55
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: TV-WZ
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: ''
                          name: Logo
                          pixel_count: 29
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: wled-yz
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.171
                          name: Logo-II
                          pixel_count: 56
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: Logo-II
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.170
                          name: YZ_QUAD_1
                          pixel_count: 292
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: yz-quad-1
                        type: wled
                    host: ''
                    offline: false
                    open-ui: false
                    port: 8080
                    sentry-crash-test: false
                    verbose: true
                    version: false
                    very-verbose: false
                    virtuals:
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Couch
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Couch
                        is_device: Couch
                        segments:
                          - - Couch
                            - 0
                            - 35
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Kitchen
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Kitchen
                        is_device: Kitchen
                        segments:
                          - - Kitchen
                            - 0
                            - 50
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: TV-WZ
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: TV-WZ
                        is_device: TV-WZ
                        segments:
                          - - TV-WZ
                            - 0
                            - 54
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Logo
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: wled-yz
                        is_device: wled-yz
                        segments:
                          - - wled-yz
                            - 0
                            - 28
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Logo-II
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Logo-II
                        is_device: Logo-II
                        segments:
                          - - Logo-II
                            - 0
                            - 55
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: YZ_QUAD_1
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: yz-quad-1
                        is_device: yz-quad-1
                        segments:
                          - - yz-quad-1
                            - 0
                            - 291
                            - false
                properties:
                  config:
                    type: string
                    minLength: 1
                  devices:
                    type: array
                    uniqueItems: true
                    minItems: 1
                    items:
                      type: object
                      properties:
                        config:
                          type: object
                          properties:
                            center_offset:
                              type: number
                            ip_address:
                              type: string
                              minLength: 1
                            name:
                              type: string
                              minLength: 1
                            pixel_count:
                              type: number
                            port:
                              type: number
                            refresh_rate:
                              type: number
                            timeout:
                              type: number
                            udp_packet_type:
                              type: string
                          required:
                            - center_offset
                            - ip_address
                            - name
                            - pixel_count
                            - port
                            - refresh_rate
                            - timeout
                            - udp_packet_type
                        id:
                          type: string
                          minLength: 1
                        type:
                          type: string
                          minLength: 1
                      required:
                        - id
                        - type
                  host:
                    type: string
                  verbose:
                    type: boolean
                  version:
                    type: boolean
                  very-verbose:
                    type: boolean
                  virtuals:
                    type: array
                    uniqueItems: true
                    minItems: 1
                    items:
                      type: object
                      properties:
                        active:
                          type: boolean
                        config:
                          type: object
                          properties:
                            center_offset:
                              type: number
                            frequency_max:
                              type: number
                            frequency_min:
                              type: number
                            icon_name:
                              type: string
                              minLength: 1
                            mapping:
                              type: string
                              minLength: 1
                            max_brightness:
                              type: number
                            name:
                              type: string
                              minLength: 1
                            preview_only:
                              type: boolean
                            transition_mode:
                              type: string
                              minLength: 1
                            transition_time:
                              type: number
                          required:
                            - center_offset
                            - frequency_max
                            - frequency_min
                            - icon_name
                            - mapping
                            - max_brightness
                            - name
                            - preview_only
                            - transition_mode
                            - transition_time
                        effect:
                          type: object
                          properties:
                            config:
                              type: object
                              required:
                                - background_color
                                - gradient_name
                                - color
                              properties:
                                background_color:
                                  type: string
                                  minLength: 1
                                gradient_name:
                                  type: string
                                color:
                                  type: string
                                  minLength: 1
                            name:
                              type: string
                              minLength: 1
                            type:
                              type: string
                              minLength: 1
                          required:
                            - config
                            - name
                            - type
                        id:
                          type: string
                          minLength: 1
                        is_device:
                          type: string
                          minLength: 1
                        segments:
                          type: array
                          items:
                            type: object
                            properties:
                              '0':
                                type: array
                                uniqueItems: true
                                items:
                                  type: object
                      required:
                        - active
                        - id
                        - is_device
                required:
                  - config
                  - devices
                  - host
                  - verbose
                  - version
                  - very-verbose
                  - virtuals
      description: Get the whole LedFx config-tree
  /devices:
    get:
      summary: GET Devices
      tags: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                description: ''
                type: object
                properties:
                  devices:
                    type: array
                    uniqueItems: true
                    minItems: 1
                    items:
                      required:
                        - id
                        - type
                      properties:
                        config:
                          type: object
                          properties:
                            center_offset:
                              type: number
                            ip_address:
                              type: string
                              minLength: 1
                            name:
                              type: string
                              minLength: 1
                            pixel_count:
                              type: number
                            port:
                              type: number
                            refresh_rate:
                              type: number
                            timeout:
                              type: number
                            udp_packet_type:
                              type: string
                          required:
                            - center_offset
                            - ip_address
                            - name
                            - pixel_count
                            - port
                            - refresh_rate
                            - timeout
                            - udp_packet_type
                        id:
                          type: string
                          minLength: 1
                        type:
                          type: string
                          minLength: 1
                required:
                  - devices
                x-examples:
                  example-1:
                    devices:
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.177
                          name: Couch
                          pixel_count: 36
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: Couch
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.178
                          name: Kitchen
                          pixel_count: 51
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: Kitchen
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.176
                          name: TV-WZ
                          pixel_count: 55
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: TV-WZ
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: ''
                          name: Logo
                          pixel_count: 29
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: wled-yz
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.171
                          name: Logo-II
                          pixel_count: 56
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: Logo-II
                        type: wled
                      - config:
                          center_offset: 0
                          ip_address: 192.168.1.170
                          name: YZ_QUAD_1
                          pixel_count: 292
                          port: 0
                          refresh_rate: 0
                          timeout: 0
                          udp_packet_type: ''
                        id: yz-quad-1
                        type: wled
      operationId: get-devices
      description: Get the whole LedFx devices-tree
  /virtuals:
    get:
      summary: GET virtuals
      tags: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                description: ''
                type: object
                properties:
                  virtuals:
                    type: array
                    uniqueItems: true
                    minItems: 1
                    items:
                      required:
                        - active
                        - id
                        - is_device
                      properties:
                        active:
                          type: boolean
                        config:
                          type: object
                          properties:
                            center_offset:
                              type: number
                            frequency_max:
                              type: number
                            frequency_min:
                              type: number
                            icon_name:
                              type: string
                              minLength: 1
                            mapping:
                              type: string
                              minLength: 1
                            max_brightness:
                              type: number
                            name:
                              type: string
                              minLength: 1
                            preview_only:
                              type: boolean
                            transition_mode:
                              type: string
                              minLength: 1
                            transition_time:
                              type: number
                          required:
                            - center_offset
                            - frequency_max
                            - frequency_min
                            - icon_name
                            - mapping
                            - max_brightness
                            - name
                            - preview_only
                            - transition_mode
                            - transition_time
                        effect:
                          type: object
                          properties:
                            config:
                              type: object
                              properties:
                                background_color:
                                  type: string
                                  minLength: 1
                                gradient_name:
                                  type: string
                                color:
                                  type: string
                                  minLength: 1
                              required:
                                - background_color
                                - gradient_name
                                - color
                            name:
                              type: string
                              minLength: 1
                            type:
                              type: string
                              minLength: 1
                          required:
                            - config
                            - name
                            - type
                        id:
                          type: string
                          minLength: 1
                        is_device:
                          type: string
                          minLength: 1
                        segments:
                          type: array
                          items:
                            required: []
                            properties:
                              '0':
                                type: array
                                uniqueItems: true
                                items:
                                  required: []
                                  properties: {}
                required:
                  - virtuals
                x-examples:
                  example-1:
                    virtuals:
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Couch
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Couch
                        is_device: Couch
                        segments:
                          - - Couch
                            - 0
                            - 35
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Kitchen
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Kitchen
                        is_device: Kitchen
                        segments:
                          - - Kitchen
                            - 0
                            - 50
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: TV-WZ
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: TV-WZ
                        is_device: TV-WZ
                        segments:
                          - - TV-WZ
                            - 0
                            - 54
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Logo
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: wled-yz
                        is_device: wled-yz
                        segments:
                          - - wled-yz
                            - 0
                            - 28
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Logo-II
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Logo-II
                        is_device: Logo-II
                        segments:
                          - - Logo-II
                            - 0
                            - 55
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: YZ_QUAD_1
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: yz-quad-1
                        is_device: yz-quad-1
                        segments:
                          - - yz-quad-1
                            - 0
                            - 291
                            - false
      operationId: get-virtuals
      description: Get the whole LedFx virtuals-tree
  '/virtuals/{virtualId}':
    get:
      summary: GET Virtual
      tags: []
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                description: ''
                type: object
                properties:
                  active:
                    type: boolean
                  config:
                    type: object
                    properties:
                      center_offset:
                        type: number
                      frequency_max:
                        type: number
                      frequency_min:
                        type: number
                      icon_name:
                        type: string
                        minLength: 1
                      mapping:
                        type: string
                        minLength: 1
                      max_brightness:
                        type: number
                      name:
                        type: string
                        minLength: 1
                      preview_only:
                        type: boolean
                      transition_mode:
                        type: string
                        minLength: 1
                      transition_time:
                        type: number
                    required:
                      - center_offset
                      - frequency_max
                      - frequency_min
                      - icon_name
                      - mapping
                      - max_brightness
                      - name
                      - preview_only
                      - transition_mode
                      - transition_time
                  effect:
                    type: object
                    properties:
                      config:
                        type: object
                        properties:
                          background_color:
                            type: string
                            minLength: 1
                          gradient_name:
                            type: string
                          color:
                            type: string
                            minLength: 1
                        required:
                          - background_color
                          - gradient_name
                          - color
                      name:
                        type: string
                        minLength: 1
                      type:
                        type: string
                        minLength: 1
                    required:
                      - config
                      - name
                      - type
                  id:
                    type: string
                    minLength: 1
                  is_device:
                    type: string
                    minLength: 1
                  segments:
                    type: array
                    items:
                      required: []
                      properties:
                        '0':
                          type: array
                          uniqueItems: true
                          items:
                            required: []
                            properties: {}
                required:
                  - active
                  - config
                  - effect
                  - id
                  - is_device
                  - segments
                x-examples:
                  example-1:
                    active: false
                    config:
                      center_offset: 0
                      frequency_max: 15000
                      frequency_min: 20
                      icon_name: wled
                      mapping: span
                      max_brightness: 1
                      name: Couch
                      preview_only: false
                      transition_mode: Add
                      transition_time: 0.4
                    effect:
                      config:
                        background_color: '#000000'
                        gradient_name: ''
                        color: '#eee000'
                      name: Single Color
                      type: singleColor
                    id: Couch
                    is_device: Couch
                    segments:
                      - - Couch
                        - 0
                        - 35
                        - false
      operationId: 'get-virtuals-virtualId]'
      description: Get virtual
    parameters:
      - schema:
          type: string
        name: virtualId
        in: path
        required: true
    put:
      summary: Set Virtual
      operationId: put-virtuals-virtualId
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                description: ''
                type: object
                properties:
                  virtuals:
                    type: array
                    uniqueItems: true
                    minItems: 1
                    items:
                      required:
                        - active
                        - id
                        - is_device
                      properties:
                        active:
                          type: boolean
                        config:
                          type: object
                          properties:
                            center_offset:
                              type: number
                            frequency_max:
                              type: number
                            frequency_min:
                              type: number
                            icon_name:
                              type: string
                              minLength: 1
                            mapping:
                              type: string
                              minLength: 1
                            max_brightness:
                              type: number
                            name:
                              type: string
                              minLength: 1
                            preview_only:
                              type: boolean
                            transition_mode:
                              type: string
                              minLength: 1
                            transition_time:
                              type: number
                          required:
                            - center_offset
                            - frequency_max
                            - frequency_min
                            - icon_name
                            - mapping
                            - max_brightness
                            - name
                            - preview_only
                            - transition_mode
                            - transition_time
                        effect:
                          type: object
                          properties:
                            config:
                              type: object
                              properties:
                                background_color:
                                  type: string
                                  minLength: 1
                                gradient_name:
                                  type: string
                                color:
                                  type: string
                                  minLength: 1
                              required:
                                - background_color
                                - gradient_name
                                - color
                            name:
                              type: string
                              minLength: 1
                            type:
                              type: string
                              minLength: 1
                          required:
                            - config
                            - name
                            - type
                        id:
                          type: string
                          minLength: 1
                        is_device:
                          type: string
                          minLength: 1
                        segments:
                          type: array
                          items:
                            required: []
                            properties:
                              '0':
                                type: array
                                uniqueItems: true
                                items:
                                  required: []
                                  properties: {}
                required:
                  - virtuals
                x-examples:
                  example-1:
                    virtuals:
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Couch
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Couch
                        is_device: Couch
                        segments:
                          - - Couch
                            - 0
                            - 35
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Kitchen
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Kitchen
                        is_device: Kitchen
                        segments:
                          - - Kitchen
                            - 0
                            - 50
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: TV-WZ
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: TV-WZ
                        is_device: TV-WZ
                        segments:
                          - - TV-WZ
                            - 0
                            - 54
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Logo
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: wled-yz
                        is_device: wled-yz
                        segments:
                          - - wled-yz
                            - 0
                            - 28
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: Logo-II
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: Logo-II
                        is_device: Logo-II
                        segments:
                          - - Logo-II
                            - 0
                            - 55
                            - false
                      - active: false
                        config:
                          center_offset: 0
                          frequency_max: 15000
                          frequency_min: 20
                          icon_name: wled
                          mapping: span
                          max_brightness: 1
                          name: YZ_QUAD_1
                          preview_only: false
                          transition_mode: Add
                          transition_time: 0.4
                        effect:
                          config:
                            background_color: '#000000'
                            gradient_name: ''
                            color: '#eee000'
                          name: Single Color
                          type: singleColor
                        id: yz-quad-1
                        is_device: yz-quad-1
                        segments:
                          - - yz-quad-1
                            - 0
                            - 291
                            - false
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties: {}
      description: Set Virtual
components:
  schemas: {}
  securitySchemes: {}
`

export default configApiYaml

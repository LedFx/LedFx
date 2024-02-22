export interface EffectDropDownProps {
  value?: string
  onChange?: (e: any) => typeof e
  groups?: any
  showFilter?: boolean
  title: string
}

export const EffectDropDownDefaultProps = {
  value: '',
  onChange: undefined,
  title: 'Effect Type',
  groups: {
    'Group 1': [
      {
        name: 'Item 1',
        id: 'item1',
        category: 'Group 1'
      },
      {
        name: 'Item2',
        id: 'item2',
        category: 'Group 1'
      }
    ],
    'Group 2': [
      {
        name: 'Item 1',
        id: 'item11',
        category: 'Group 2'
      }
    ]
  },
  showFilter: false
}

import React from 'react'
import { Settings } from '@mui/icons-material'
import { TransitionProps } from '@mui/material/transitions'
import { MenuItem, Slide } from '@mui/material'

export interface SpotifyScreenProps {
  icon: React.ReactElement
  startIcon: React.ReactElement
  label: string
  type: string
  className: string
  // eslint-disable-next-line prettier/prettier
  color: 'primary' | 'inherit' | 'error' | 'success' | 'warning' | 'info' | 'secondary' | undefined;
  variant: 'outlined' | 'text' | 'contained' | undefined
  innerKey: string
  disabled: boolean
  size: 'small' | 'medium' | 'large' | undefined
}

export const SpotifyScreenDefaultProps = {
  icon: <Settings />,
  startIcon: undefined,
  label: '',
  type: 'button',
  className: undefined,
  color: 'primary',
  variant: 'contained',
  innerKey: undefined,
  disabled: false,
  size: 'small'
}

export const Transition = React.forwardRef(function Transition(
  props: TransitionProps & { children?: React.ReactElement },
  ref: React.Ref<unknown>
) {
  return <Slide direction="up" ref={ref} {...(props as any)} />
})

Transition.defaultProps = {
  children: <div>loading</div>
}

export const MuiMenuItem = React.forwardRef(
  (props: any, ref: React.Ref<unknown>) => {
    return <MenuItem ref={ref} {...props} />
  }
)

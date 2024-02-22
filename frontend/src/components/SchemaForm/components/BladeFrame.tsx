import { styled } from '@mui/material/styles'
import { ReactElement } from 'react'

const Root = styled('div')(({ theme }) => ({
  minWidth: '23.5%',
  padding: '16px 1.2rem 6px 1.2rem',
  border: '1px solid',
  borderColor: theme.palette.divider,
  borderRadius: '10px',
  position: 'relative',
  display: 'flex',
  alignItems: 'center',
  height: 'auto',
  margin: '0.5rem 0',
  '@media (max-width: 580px)': {
    width: '100% !important',
    margin: '0.5rem 0'
  },
  '& > label': {
    top: '-0.75rem',
    display: 'flex',
    alignItems: 'center',
    left: '1rem',
    padding: '0 0.3rem',
    position: 'absolute',
    fontVariant: 'all-small-caps',
    fontSize: '0.9rem',
    letterSpacing: '0.1rem',
    color: theme.palette.text.secondary,
    backgroundColor: theme.palette.background.paper,
    boxSizing: 'border-box'
  }
}))

interface BladeFrameProps {
  title?: string
  index?: number
  children?: any
  full?: boolean
  style?: any
  required?: boolean
  variant?: 'outlined' | 'contained' | 'inherit'
  className?: string | undefined
  disabled?: boolean
  labelStyle?: any
  onClick?: any | undefined
}

const BladeFrame = ({
  index,
  title,
  children,
  full = false,
  style = { width: 'unset', order: 0 },
  required = false,
  variant = 'outlined',
  className,
  disabled,
  labelStyle = {},
  onClick
}: BladeFrameProps): ReactElement<any, any> => {
  return variant === 'outlined' ? (
    <Root
      className={className || ''}
      style={{
        ...style,
        width: full ? '100%' : style.width
      }}
      onClick={onClick}
    >
      <label
        style={{ ...labelStyle }}
        className={`MuiFormLabel-root${
          disabled ? ' Mui-disabled' : ''
        }  step-effect-${index}`}
      >
        {title}
        {required ? '*' : ''}
      </label>
      {children}
    </Root>
  ) : (
    children
  )
}

BladeFrame.defaultProps = {
  index: undefined,
  title: undefined,
  children: undefined,
  full: false,
  style: {
    width: 'unset',
    order: 0
  },
  required: false,
  variant: 'outlined',
  className: undefined,
  disabled: undefined,
  labelStyle: undefined,
  onClick: undefined
}

export default BladeFrame

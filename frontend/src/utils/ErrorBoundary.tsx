/* eslint-disable react/require-default-props */
/* eslint-disable react/destructuring-assignment */
import React, { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children?: ReactNode
}

interface State {
  hasError: boolean
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(_: Error) {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.warn(error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            maxWidth: 360,
            width: '100%',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            textAlign: 'center',
            margin: '0 auto',
            paddingTop: '3rem'
          }}
        >
          <h1>Something went wrong</h1>
          <p>
            Deleting the browser&apos;s frontend-data might help,
            <br />
            if there is old config data left.
          </p>
          <p> Refresh page after clearing data... </p>
          <button
            type="button"
            style={{
              height: 40,
              borderRadius: 10,
              border: '1px solid #999',
              color: '#fff',
              backgroundColor: '#600000',
              cursor: 'pointer'
            }}
            onClick={() => {
              window.localStorage.removeItem('undefined')
              window.localStorage.removeItem('ledfx-storage')
              window.localStorage.removeItem('ledfx-host')
              window.localStorage.removeItem('ledfx-hosts')
              window.localStorage.removeItem('ledfx-frontend')
              window.localStorage.removeItem('ledfx-cloud-role')
              window.localStorage.removeItem('ledfx-cloud-userid')
              window.localStorage.removeItem('ledfx-theme')
              window.localStorage.removeItem('jwt')
              window.localStorage.removeItem('username')
              window.localStorage.removeItem('BladeMod')
              window.location.reload()
            }}
          >
            Clear Browser-Data
          </button>
          <br />
          <button
            type="button"
            style={{
              height: 40,
              borderRadius: 10,
              border: '1px solid #999',
              color: '#fff',
              backgroundColor: '#600000',
              cursor: 'pointer'
            }}
            onClick={() => {
              window.location.reload()
            }}
          >
            Just refresh
          </button>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary

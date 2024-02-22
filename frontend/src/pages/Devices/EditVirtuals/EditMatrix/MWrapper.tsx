import { Alert } from '@mui/material'

const MWrapper = ({ children }: any) => {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        flexDirection: 'column',
        maxHeight: '80vh'
      }}
    >
      <Alert severity="info" sx={{ width: 500, marginBottom: 2 }}>
        <strong>Concept Draft</strong>
        <ul style={{ padding: '0 1rem' }}>
          <li>Use Mousewheel to Zoom</li>
          <li>Use left-click with drag&drop to move around</li>
          <li>Use right-click to assign Pixels</li>
        </ul>
      </Alert>
      {children}
    </div>
  )
}

export default MWrapper

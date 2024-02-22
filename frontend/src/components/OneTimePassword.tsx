import { useCallback, useEffect, useState } from 'react'
import OtpInput from 'react-otp-input'
import isElectron from 'is-electron'

const OneTimePassword = ({ enabled }: { enabled: boolean }) => {
  if (!isElectron()) return null
  const [otp, setOtp] = useState('')
  const [invalidCode, setInvalidCode] = useState(false)
  const [qrCodePng, setQrCodePng] = useState(null)

  const user = {
    username: 'FreeUser',
    mfaEnabled: false,
    mfaSecret: null
  }

  const handleSubmit = useCallback(async () => {
    ;(window as any).api?.send('toMain', {
      command: 'verify_otp',
      token: otp
    })
  }, [otp])

  useEffect(() => {
    if (otp.length === 6) handleSubmit()
  }, [otp])

  useEffect(() => {
    ;(window as any).api?.send('toMain', {
      command: 'generate-mfa-qr',
      user
    })
    ;(window as any).api?.receive('fromMain', (args: any) => {
      if (args[0] === 'mfa-verified') {
        setInvalidCode(!args[1])
        if (args[1]) {
          window.localStorage.removeItem('lock')
          window.location.reload()
        }
        if (args[0] === 'mfa-qr-code') {
          setQrCodePng(args[1])
        }
      }
    })
  }, [])

  return (
    <div>
      {!enabled && (
        <div>{qrCodePng && <img src={qrCodePng} alt="MFA QR Code" />}</div>
      )}

      <form onSubmit={handleSubmit}>
        <OtpInput
          containerStyle={{ display: 'flex', justifyContent: 'center' }}
          shouldAutoFocus
          value={otp}
          onChange={setOtp}
          numInputs={6}
          renderInput={(props, index) => (
            <>
              <input
                {...props}
                style={{
                  width: '70px',
                  height: '95px',
                  borderRadius: '4px',
                  border: '1px solid #666',
                  backgroundColor: '#000',
                  color: '#fff',
                  fontWeight: 'bold',
                  fontSize: '40px',
                  textAlign: 'center'
                }}
              />
              {index !== 5 && <span style={{ marginRight: 20 }} />}
              {index === 2 && (
                <span style={{ margin: '0 30px 0 10px' }}>-</span>
              )}
            </>
          )}
        />
        {invalidCode && <p>Invalid verification code</p>}
      </form>
    </div>
  )
}

export default OneTimePassword

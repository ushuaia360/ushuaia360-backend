"""
Email service using Resend
"""
import httpx
from quart import current_app


async def send_verification_email(email: str, token: str):
    """Send email verification email"""
    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    scheme = (current_app.config.get('MOBILE_DEEP_LINK_SCHEME') or 'ushuaia360').strip().rstrip(':/')
    web_link = f"{frontend_url}/verify?token={token}"
    app_link = f"{scheme}://verify?token={token}"
    subject = "Verificá tu cuenta en Ushuaia360"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f7fa;">
        <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f5f7fa; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table role="presentation" style="background-color: #ffffff; width: 100%; max-width: 600px; border-collapse: collapse; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 40px 30px; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700; letter-spacing: -0.5px;">
                                    Ushuaia360
                                </h1>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <h2 style="margin: 0 0 20px 0; color: #1e293b; font-size: 24px; font-weight: 600;">
                                    ¡Bienvenido a Ushuaia360!
                                </h2>
                                <p style="margin: 0 0 20px 0; color: #64748b; font-size: 16px; line-height: 1.6;">
                                    Hola,
                                </p>
                                <p style="margin: 0 0 30px 0; color: #64748b; font-size: 16px; line-height: 1.6;">
                                    Gracias por crear tu cuenta en <strong style="color: #1e3a8a;">Ushuaia360</strong>. 
                                    Para completar tu registro y activar tu cuenta, por favor verificá tu dirección de email haciendo clic en el botón de abajo.
                                </p>
                                
                                <!-- CTA Button -->
                                <table role="presentation" style="width: 100%; margin: 30px 0;">
                                    <tr>
                                        <td align="center" style="padding: 20px 0;">
                                            <a href="{web_link}" style="display: inline-block; background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: #ffffff; text-decoration: none; padding: 16px 40px; border-radius: 8px; font-size: 16px; font-weight: 600; box-shadow: 0 4px 12px rgba(30, 58, 138, 0.3); transition: all 0.3s;">
                                                Verificar mi cuenta
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="margin: 30px 0 0 0; color: #64748b; font-size: 14px; line-height: 1.6;">
                                    Este enlace estará disponible por <strong style="color: #f97316;">24 horas</strong>.
                                </p>
                                
                                <p style="margin: 24px 0 0 0; color: #64748b; font-size: 14px; line-height: 1.6;">
                                    ¿Tenés la app instalada? <a href="{app_link}" style="color: #3b82f6; font-weight: 600;">Verificar en la app</a>
                                </p>
                                <p style="margin: 20px 0 0 0; color: #94a3b8; font-size: 14px; line-height: 1.6;">
                                    Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
                                    <a href="{web_link}" style="color: #3b82f6; word-break: break-all;">{web_link}</a>
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8fafc; padding: 30px; text-align: center; border-top: 1px solid #e2e8f0;">
                                <p style="margin: 0 0 10px 0; color: #64748b; font-size: 14px;">
                                    ¿Tenés alguna duda? Contactanos cuando quieras.
                                </p>
                                <p style="margin: 20px 0 0 0; color: #1e293b; font-size: 14px; font-weight: 600;">
                                    Gracias por confiar en Ushuaia360
                                </p>
                                <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 12px;">
                                    El equipo de Ushuaia360
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    resend_api_key = current_app.config.get('RESEND_API_KEY')
    resend_from = current_app.config.get('RESEND_FROM_EMAIL', 'noreply@ushuaia360.com')
    
    if not resend_api_key:
        raise ValueError("RESEND_API_KEY must be set in configuration")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_api_key}"},
            json={
                "from": resend_from,
                "to": [email],
                "subject": subject,
                "html": html,
            },
        )
        response.raise_for_status()


async def send_password_reset_email(email: str, token: str):
    """Send password reset email"""
    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    scheme = (current_app.config.get('MOBILE_DEEP_LINK_SCHEME') or 'ushuaia360').strip().rstrip(':/')
    web_link = f"{frontend_url}/reset-password?token={token}"
    app_link = f"{scheme}://reset-password?token={token}"
    subject = "Restablecé tu contraseña en Ushuaia360"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f7fa;">
        <table role="presentation" style="width: 100%; border-collapse: collapse; background-color: #f5f7fa; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table role="presentation" style="background-color: #ffffff; width: 100%; max-width: 600px; border-collapse: collapse; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); padding: 40px 30px; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 32px; font-weight: 700; letter-spacing: -0.5px;">
                                    Ushuaia360
                                </h1>
                            </td>
                        </tr>
                        
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <h2 style="margin: 0 0 20px 0; color: #1e293b; font-size: 24px; font-weight: 600;">
                                    Restablecer contraseña
                                </h2>
                                <p style="margin: 0 0 20px 0; color: #64748b; font-size: 16px; line-height: 1.6;">
                                    Hola,
                                </p>
                                <p style="margin: 0 0 30px 0; color: #64748b; font-size: 16px; line-height: 1.6;">
                                    Recibimos una solicitud para restablecer tu contraseña en <strong style="color: #1e3a8a;">Ushuaia360</strong>. 
                                    Si fuiste vos, hacé clic en el botón de abajo para crear una nueva contraseña.
                                </p>
                                
                                <!-- CTA Button -->
                                <table role="presentation" style="width: 100%; margin: 30px 0;">
                                    <tr>
                                        <td align="center" style="padding: 20px 0;">
                                            <a href="{web_link}" style="display: inline-block; background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: #ffffff; text-decoration: none; padding: 16px 40px; border-radius: 8px; font-size: 16px; font-weight: 600; box-shadow: 0 4px 12px rgba(30, 58, 138, 0.3);">
                                                Restablecer contraseña
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="margin: 30px 0 0 0; color: #64748b; font-size: 14px; line-height: 1.6;">
                                    Este enlace estará disponible por <strong style="color: #f97316;">1 hora</strong>.
                                </p>
                                
                                <p style="margin: 24px 0 0 0; color: #64748b; font-size: 14px; line-height: 1.6;">
                                    ¿Tenés la app instalada? <a href="{app_link}" style="color: #3b82f6; font-weight: 600;">Restablecer en la app</a>
                                </p>
                                <p style="margin: 20px 0 0 0; color: #94a3b8; font-size: 14px; line-height: 1.6;">
                                    Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
                                    <a href="{web_link}" style="color: #3b82f6; word-break: break-all;">{web_link}</a>
                                </p>
                                
                                <p style="margin: 30px 0 0 0; color: #ef4444; font-size: 14px; line-height: 1.6;">
                                    <strong>Importante:</strong> Si no realizaste esta solicitud, podés ignorar este mensaje. Tu contraseña no será cambiada.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8fafc; padding: 30px; text-align: center; border-top: 1px solid #e2e8f0;">
                                <p style="margin: 0 0 10px 0; color: #64748b; font-size: 14px;">
                                    ¿Tenés alguna duda? Contactanos cuando quieras.
                                </p>
                                <p style="margin: 20px 0 0 0; color: #1e293b; font-size: 14px; font-weight: 600;">
                                    Gracias por confiar en Ushuaia360
                                </p>
                                <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 12px;">
                                    El equipo de Ushuaia360
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    resend_api_key = current_app.config.get('RESEND_API_KEY')
    resend_from = current_app.config.get('RESEND_FROM_EMAIL', 'noreply@ushuaia360.com')
    
    if not resend_api_key:
        raise ValueError("RESEND_API_KEY must be set in configuration")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_api_key}"},
            json={
                "from": resend_from,
                "to": [email],
                "subject": subject,
                "html": html,
            },
        )
        response.raise_for_status()

import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Logo CHRISCO. `onDark` cambia el color del texto para fondos oscuros. */
@Component({
  selector: 'app-logo',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg
      viewBox="0 0 260 210"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="CHRISCO Constructora"
    >
      <g transform="translate(10, 5)">
        <path
          d="M72 18 L122 68 L98 92 L76 70 L48 98 L88 138 L104 122 L120 138 L88 170 C80 178 68 178 60 170 L14 124 C6 116 6 104 14 96 L60 50 C68 42 80 42 88 50"
          fill="#4A4F54"
        />
        <path
          d="M148 18 C156 10 168 10 176 18 L222 64 C230 72 230 84 222 92 L176 138 C168 146 156 146 148 138 L124 114 L148 90 L160 102 L188 74 L148 34 L132 50 L116 34 L148 2 C156 -6 168 -6 176 2"
          fill="#F58220"
        />
      </g>
      <text
        x="130"
        y="180"
        font-family="'Arial Black', Impact, sans-serif"
        font-weight="900"
        font-size="34"
        [attr.fill]="onDark() ? '#FFFFFF' : '#212B30'"
        text-anchor="middle"
        letter-spacing="2"
      >
        CHRISCO
      </text>
      <rect x="20" y="188" width="220" height="15" rx="3" fill="#F58220" />
      <text
        x="130"
        y="199.5"
        font-family="'Arial Black', sans-serif"
        font-weight="800"
        font-size="9"
        fill="#FFFFFF"
        text-anchor="middle"
        letter-spacing="6"
      >
        CONSTRUCTORA
      </text>
    </svg>
  `,
  styles: `
    :host {
      display: inline-block;
    }
    svg {
      height: 100%;
      width: auto;
    }
  `,
})
export class Logo {
  readonly onDark = input(false);
}

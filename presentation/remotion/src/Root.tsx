import { Composition } from "remotion";
import { Deck } from "./Deck";

export const RemotionRoot = () => {
  return (
    <Composition
      id="CareLoopDeck"
      component={Deck}
      durationInFrames={11 * 120}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};

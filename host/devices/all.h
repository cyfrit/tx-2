// Register concrete types so the host can specialize its per-clock bus sampler.
#pragma once
#include "random.h"
#include "punch.h"
#include "plotter.h"
#include "writer_keys.h"
#include "misc.h"
#include "magnetic_tape.h"
#include "xerox.h"
#include "datrac.h"
#include <tuple>

inline auto make_devices() {
    auto first_writer = std::make_shared<WriterMechanism>();
    auto second_writer = std::make_shared<WriterMechanism>();
    return std::tuple{
        std::make_unique<Random>(), std::make_unique<Punch>(), std::make_unique<Plotter>(),
        std::make_unique<Tx2MagTape>(), std::make_unique<IbmMagTape>(),
        std::make_unique<Xerox>(), std::make_unique<Datrac>(),
        std::make_unique<WriterKeys>(065, "lw65", first_writer), std::make_unique<WriterOutput>(066, "lw66", first_writer),
        std::make_unique<WriterKeys>(071, "lw71", second_writer), std::make_unique<WriterOutput>(072, "lw72", second_writer),
        std::make_unique<MiscIn>(), std::make_unique<MiscOut>()};
}
